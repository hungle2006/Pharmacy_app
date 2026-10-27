'use strict';
const { neon } = require('@neondatabase/serverless');

// Search text only selects possible ICD diagnoses. NEVER infer a diagnosis or
// treatment from edit-distance similarity; a user must choose the ICD entry.
const normalize = value => String(value || '').toLowerCase()
  .replace(/đ/g,'d').normalize('NFD').replace(/[\u0300-\u036f]/g,'')
  .replace(/[^a-z0-9]+/g,' ').trim().replace(/\s+/g,' ');
const unique = values => [...new Set(values.filter(Boolean))];
const codeFormat = value => String(value||'').toUpperCase().trim().replace(/[^A-Z0-9.]/g,'');
const trigrams = value => {
  const s = '  ' + value + ' ';
  const out = new Set();
  for (let i=0;i<s.length-2;i++) out.add(s.slice(i,i+3));
  return out;
};
const dice = (a,b) => {
  if (!a || !b) return 0;
  const A = trigrams(a), B = trigrams(b);
  let intersect=0; for (const t of A) if (B.has(t)) intersect++;
  return (2*intersect)/(A.size+B.size);
};
const aliases = {
  'hen suyen':'hen phe quan',
  'hen':'hen phe quan',
  'tieu duong':'dai thao duong',
  'cao huyet ap':'tang huyet ap',
  'huyet ap cao':'tang huyet ap',
  'benh tim mach':'tim mach'
};
function rankDisease(row, raw) {
  const query = normalize(raw);
  const q = aliases[query] || query;
  const vi = normalize(row.disease_name_vi || row.disease_name_vi_norm);
  const en = normalize(row.disease_name_en || row.disease_name_en_norm);
  const code = codeFormat(raw);
  const codeNoDot = code.replace(/\./g,'');
  if (code && (code === row.icd_code || codeNoDot === row.icd_code_nodot)) return 100;
  const words = unique(q.split(' ').filter(w => w.length>=2));
  const score = val => {
    if (!val) return 0;
    if (val === q) return 95;
    const tokens = val.split(' ');
    const matched = words.filter(w=>tokens.some(v=>v===w || (w.length>=4 && dice(w,v)>0.72))).length;
    const coverage = words.length ? matched/words.length : 0;
    const similarity = dice(q,val);
    let s = 20*coverage+55*similarity;
    if (val.startsWith(q+' ')) s+=18;
    else if (val.includes(q)) s+=12;
    if (q.includes(val) && val.length>=6) s+=4;
    const extraWords = Math.max(0, tokens.length - words.length);
    s -= Math.min(9,extraWords*1.2);
    // Do not promote pregnancy/newborn variants for a generic disease query.
    for (const qualifier of ['thai ky','tre so sinh']) {
      if (val.includes(qualifier) && !q.includes(qualifier)) s -= 15;
    }
    return Math.max(0,Math.min(94,s));
  };
  return Math.max(score(vi),score(en));
}
function sqlClient() {
  if (!process.env.DATABASE_URL) return null;
  return neon(process.env.DATABASE_URL);
}
const responseHeaders = res => {
  res.setHeader('Cache-Control','private, no-store');
  res.setHeader('X-Content-Type-Options','nosniff');
};
async function findDiseases(sql, raw) {
  const normalized=normalize(raw);
  if (normalized.length < 2 || normalized.length > 100) return [];
  const query=aliases[normalized]||normalized;
  const terms=unique(query.split(' ').filter(t=>t.length>=3)).sort((a,b)=>b.length-a.length).slice(0,5);
  const fragments=[query,...terms].filter(Boolean);
  const predicates=['upper(icd_code)=$1','upper(icd_code_nodot)=$1'];
  const params=[codeFormat(raw).replace(/\./g,'')];
  for (const token of fragments) {
    params.push('%'+token+'%');
    const i=params.length;
    predicates.push('disease_name_vi_norm ILIKE $'+i);
    predicates.push('disease_name_en_norm ILIKE $'+i);
  }
  const statement = 'SELECT icd_code, icd_code_nodot, disease_name_vi, disease_name_vi_norm, disease_name_en, disease_name_en_norm, chapter_code FROM public.disease WHERE '+
    predicates.join(' OR ')+
    ' ORDER BY CASE WHEN upper(icd_code_nodot)=$1 THEN 0 WHEN disease_name_vi_norm ILIKE $2 THEN 1 ELSE 2 END, length(coalesce(disease_name_vi_norm, \'\')) LIMIT 1800';
  const rows=await sql.query(statement,params);
  const ranked=rows.map(row=>({...row, matchScore: rankDisease(row,raw)}))
    .filter(row=>row.matchScore>=26)
    .sort((a,b)=>b.matchScore-a.matchScore || (a.disease_name_vi||'').length-(b.disease_name_vi||'').length || a.icd_code.localeCompare(b.icd_code));
  return ranked.slice(0,15).map(({icd_code,disease_name_vi,disease_name_en,chapter_code,matchScore})=>({
    icd_code,disease_name_vi,disease_name_en,chapter_code,
    match_level:matchScore>=94?'exact':matchScore>=65?'close':'possible'
  }));
}
async function findRelated(sql, code) {
  const diseaseRows=await sql.query('SELECT icd_code, disease_name_vi, disease_name_en, chapter_code FROM public.disease WHERE icd_code=$1 LIMIT 1',[code]);
  if (!diseaseRows.length) return null;
  const filter = "m.disease_icd_code=$1 AND m.code_system='ICD10CM' AND m.icd_match_status='EXACT_ICD10_CODE' AND m.rxnorm_match_status='FOUND_IN_RXNORM_SNAPSHOT'";
  // These are literature/data associations, not validated treatment orders.
  const medications=await sql.query(
    'SELECT m.rxcui, MAX(NULLIF(m.drug_description,\'\')) AS drug_description, '+
    'MAX(NULLIF(m.indication_description,\'\')) AS indication_description, '+
    'MAX(NULLIF(r.canonical_name,\'\')) AS rxnorm_name '+
    'FROM public.medi_relation m LEFT JOIN public.rxnorm_concept r ON r.rxcui=m.rxcui WHERE '+filter+
    ' GROUP BY m.rxcui ORDER BY drug_description NULLS LAST, m.rxcui LIMIT 100',[code]);
  // Only product links already ACCEPTED in Gold are displayed. The links
  // identify products containing an ingredient with a MEDI association;
  // they do NOT attest indication, suitability, or interchangeability.
  const products=await sql.query(
    'WITH med AS (SELECT DISTINCT m.rxcui FROM public.medi_relation m WHERE '+filter+'), '+
    'candidates AS (SELECT dm.dav_row_id, c.ingredient_rxcui FROM med '+
    'JOIN public.rxnorm_scd_component c ON c.ingredient_rxcui=med.rxcui '+
    'JOIN public.dav_rxnorm_mapping dm ON dm.selected_scd_rxcui=c.scd_rxcui '+
    'WHERE dm.accepted_for_serving=1 AND dm.selected_scd_rxcui IS NOT NULL) '+
    'SELECT p.dav_row_id AS id,p.drug_name,p.registration_number,p.active_ingredient_raw AS ingredient,'+
    'p.strength_raw AS strength,p.dosage_form_raw AS dosage_form,p.manufacturer,'+
    'COUNT(DISTINCT ca.ingredient_rxcui)::integer AS linked_ingredients '+
    'FROM candidates ca JOIN public.dav_product p ON p.dav_row_id=ca.dav_row_id '+
    'GROUP BY p.dav_row_id ORDER BY linked_ingredients DESC,p.drug_name NULLS LAST,p.dav_row_id LIMIT 35',[code]);
  return {disease:diseaseRows[0],medications,products,
    evidence_scope:'MEDI ICD-10-CM exact-code relations to RxNorm. DAV products appear only for a Gold-accepted RxNorm SCD containing a related ingredient.',
    important_note:'Đây là dữ liệu liên quan hoạt chất–bệnh, KHÔNG xác nhận sản phẩm DAV có chỉ định điều trị bệnh này. Không dùng để tự chọn thuốc, chẩn đoán hay kê đơn.'};
}
async function handler(req,res) {
  responseHeaders(res);
  if (req.method!=='GET') return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
  const sql=sqlClient();
  if (!sql) return res.status(503).json({error:'DATABASE_UNAVAILABLE'});
  try {
    const code=codeFormat(req.query?.icd).slice(0,20);
    if (code) {
      if (!/^[A-Z][0-9]{2}(?:\.[A-Z0-9]{1,5})?$/.test(code)) return res.status(400).json({error:'INVALID_ICD_CODE'});
      const result=await findRelated(sql,code);
      if (!result) return res.status(404).json({error:'ICD_NOT_FOUND'});
      return res.status(200).json({mode:'database',scope:'disease_evidence',...result});
    }
    const q=typeof req.query?.q==='string'?req.query.q.trim():'';
    if (q.length<2 || q.length>100) return res.status(400).json({error:'QUERY_LENGTH',notice:'Nhập từ 2 đến 100 ký tự.'});
    const suggestions=await findDiseases(sql,q);
    return res.status(200).json({mode:'database',scope:'disease_suggestions',q,suggestions,requiresSelection:true,
      note:'Các kết quả chỉ là gợi ý tên bệnh, cần chọn đúng mã ICD; không tự xác định chẩn đoán.'});
  } catch(error) {
    console.error('Disease lookup failed',error?.name||'error',error?.code||'unknown');
    return res.status(503).json({error:'QUERY_FAILED',notice:'Không đọc được dữ liệu từ Neon Gold. Thử lại sau.'});
  }
}
module.exports=handler;
module.exports.normalize=normalize;
module.exports.rankDisease=rankDisease;
module.exports.findDiseases=findDiseases;
