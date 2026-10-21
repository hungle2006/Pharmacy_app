'use strict';
const { neon } = require('@neondatabase/serverless');

const pageNumber=value=>{
  const n=Number(value);
  return Number.isSafeInteger(n)&&n>0?Math.min(n,100000):1;
};
const pageSizeNumber=value=>{
  const n=Number(value);
  return Number.isSafeInteger(n)&&n>0?Math.min(n,100):25;
};
const escapeLike=x=>String(x).replace(/[\\%_]/g,'\\$&');

// Read-only RxNorm terminology discovery. A text candidate is not a verified drug mapping.
function buildConceptQuery(query={}) {
  const q=typeof query.q==='string'?query.q.trim().slice(0,120):'';
  if(!q)return null;
  const page=pageNumber(query.page),pageSize=pageSizeNumber(query.pageSize);
  const term='%'+escapeLike(q)+'%';
  const predicate="(c.canonical_name ILIKE $1 OR c.rxcui = $2)";
  const from="FROM public.rxnorm_concept c WHERE "+predicate;
  return {
    page,pageSize,
    countSql:"SELECT COUNT(*)::bigint AS total_rows "+from,
    countParams:[term,q],
    rowsSql:[
      "SELECT c.rxcui, c.canonical_name, c.canonical_tty, c.canonical_sab,",
      "c.tty_set, c.sab_set, c.is_ingredient, c.is_scd,",
      "s.scd_name, s.component_count, s.component_status,",
      "s.dose_form_name",
      "FROM public.rxnorm_concept c",
      "LEFT JOIN public.rxnorm_scd s ON s.scd_rxcui=c.rxcui",
      "WHERE "+predicate,
      "ORDER BY CASE WHEN LOWER(c.canonical_name)=LOWER($2) THEN 0",
      "WHEN c.rxcui=$2 THEN 0 ELSE 1 END, c.canonical_name, c.rxcui",
      "LIMIT $3 OFFSET $4"
    ].join(' '),
    params:[term,q,pageSize,(page-1)*pageSize]
  };
}

// Reverse lookup uses EXPLICIT Gold evidence only (no fuzzy name-based substitution).
// SCD matches reference either reviewed selected IDs or unverified suggested IDs.
// Ingredient search references component evidence, not official RXNREL.
function buildDavReverseQuery({rxcui,kind='scd',review='all',page=1,pageSize=10}={}) {
  if(!/^[0-9]{1,15}$/.test(String(rxcui||''))) return null;
  const currentPage=pageNumber(page), size=Math.min(50,pageSizeNumber(pageSize));
  const scope=kind==='ingredient'?'ingredient':kind==='scd'?'scd':'unsupported';
  const reviewFilter=['all','accepted','review'].includes(review)?review:'all';
  const links=[
    "WITH links AS (",
    "SELECT m.dav_row_id, 'ACCEPTED_SCD'::text AS match_type, 0 AS priority",
    "FROM public.dav_rxnorm_mapping m",
    "WHERE m.selected_scd_rxcui=$1 AND m.accepted_for_serving=1 AND $2='scd'",
    "UNION ALL",
    "SELECT m.dav_row_id, 'CANDIDATE_SCD'::text AS match_type, 1 AS priority",
    "FROM public.dav_rxnorm_mapping m",
    "WHERE m.suggested_scd_rxcui=$1 AND COALESCE(m.accepted_for_serving,0)<>1 AND $2='scd'",
    "UNION ALL",
    "SELECT e.dav_row_id, 'INGREDIENT_EVIDENCE'::text AS match_type, 2 AS priority",
    "FROM public.dav_rxnorm_evidence e",
    "WHERE e.ingredient_candidate_rxcui=$1 AND $2='ingredient'",
    "), best AS (",
    "SELECT DISTINCT ON (dav_row_id) dav_row_id,match_type",
    "FROM links ORDER BY dav_row_id,priority",
    "), filtered AS (",
    "SELECT b.dav_row_id,b.match_type FROM best b",
    "JOIN public.dav_product d ON d.dav_row_id=b.dav_row_id",
    "WHERE ($3='all' OR ($3='accepted' AND b.match_type='ACCEPTED_SCD')",
    "OR ($3='review' AND b.match_type<>'ACCEPTED_SCD'))",
    ")"
  ].join(' ');
  return {
    page:currentPage,pageSize:size,kind:scope,review:reviewFilter,
    countSql:links+" SELECT COUNT(*)::bigint AS total_rows FROM filtered",
    countParams:[String(rxcui),scope,reviewFilter],
    rowsSql:links+[
      "SELECT d.dav_row_id AS id, d.drug_name, d.registration_number AS registration_no,",
      "d.active_ingredient_raw AS ingredient, d.strength_raw AS strength,",
      "d.dosage_form_raw AS dosage_form, d.manufacturer, d.source AS product_source,",
      "d.catalog_duplicate_status, f.match_type,",
      "p.price_vnd, p.price_type, p.declaration_date AS snapshot_date,",
      "COALESCE(NULLIF(p.unit,''),NULLIF(d.unit,'')) AS unit",
      "FROM filtered f JOIN public.dav_product d ON d.dav_row_id=f.dav_row_id",
      "LEFT JOIN LATERAL (",
      "SELECT pr.price_vnd,pr.price_type,pr.declaration_date,pr.unit",
      "FROM public.price_record pr WHERE pr.dav_row_id=d.dav_row_id",
      "ORDER BY pr.declaration_date DESC NULLS LAST,pr.price_id DESC LIMIT 1",
      ") p ON true",
      "ORDER BY CASE f.match_type WHEN 'ACCEPTED_SCD' THEN 0",
      "WHEN 'CANDIDATE_SCD' THEN 1 ELSE 2 END, d.drug_name NULLS LAST, d.dav_row_id",
      "LIMIT $4 OFFSET $5"
    ].join(' '),
    params:[String(rxcui),scope,reviewFilter,size,(currentPage-1)*size]
  };
}

async function handler(req,res) {
  res.setHeader('Cache-Control','private, no-store');
  if(req.method!=='GET')return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
  if(!process.env.DATABASE_URL)return res.status(503).json({
    mode:'unavailable',reason:'DATABASE_URL_MISSING'
  });
  try {
    const sql=neon(process.env.DATABASE_URL);
    const productId=typeof req.query?.dav_row_id==='string'?
      req.query.dav_row_id.trim().slice(0,100):'';
    if(productId) {
      const [products,evidence]=await Promise.all([
        sql.query([
          "SELECT d.dav_row_id, d.drug_name, d.registration_number,",
          "d.active_ingredient_raw, d.strength_raw, d.dosage_form_raw,",
          "d.silver_qc_status, d.catalog_duplicate_status,",
          "m.selected_scd_rxcui, m.selected_scd_name,",
          "m.suggested_scd_rxcui, m.candidate_scd_name,",
          "m.accepted_for_serving, m.mapping_status, m.silver_mapping_status,",
          "m.candidate_evidence_status, m.ingredient_component_total,",
          "m.ingredient_component_matched, m.review_reason,",
          "s.scd_name AS terminology_scd_name, s.dose_form_name",
          "FROM public.dav_product d",
          "LEFT JOIN public.dav_rxnorm_mapping m ON m.dav_row_id=d.dav_row_id",
          "LEFT JOIN public.rxnorm_scd s",
          "ON s.scd_rxcui=COALESCE(NULLIF(m.selected_scd_rxcui,''),",
          "NULLIF(m.suggested_scd_rxcui,''))",
          "WHERE d.dav_row_id=$1 LIMIT 1"
        ].join(' '),[productId]),
        sql.query([
          "SELECT component_order, component_raw, ingredient_search_name,",
          "ingredient_candidate_rxcui, ingredient_candidate_name, ingredient_candidate_tty,",
          "candidate_count, match_method, evidence_status, review_reason, clinical_verified",
          "FROM public.dav_rxnorm_evidence WHERE dav_row_id=$1",
          "ORDER BY component_order ASC LIMIT 100"
        ].join(' '),[productId])
      ]);
      const product=products[0]||null;
      if(!product)return res.status(404).json({error:'DAV_PRODUCT_NOT_FOUND'});
      return res.status(200).json({
        mode:'database',scope:'product_rxnorm_evidence',product,evidence,
        clinicalNote:'Ứng viên tự động chưa được xác minh lâm sàng. Chỉ mapping accepted_for_serving=1 là trạng thái được Gold ghi nhận đã duyệt; luôn kiểm tra nguồn bằng chứng.'
      });
    }
    // Reverse direction: RxNorm SCD / ingredient evidence -> related DAV products.
    const reverseRx=typeof req.query?.dav_for_rxcui==='string'
      ?req.query.dav_for_rxcui.trim():'';
    if(reverseRx) {
      if(!/^[0-9]{1,15}$/.test(reverseRx))
        return res.status(400).json({error:'INVALID_RXCUI'});
      const found=await sql.query(
        "SELECT rxcui,canonical_name,canonical_tty,is_scd,is_ingredient FROM public.rxnorm_concept WHERE rxcui=$1 LIMIT 1",
        [reverseRx]
      );
      if(!found.length)return res.status(404).json({error:'RXCUI_NOT_FOUND'});
      const concept=found[0];
      const kind=Number(concept.is_scd)===1?'scd':
        Number(concept.is_ingredient)===1?'ingredient':'unsupported';
      const reverse=buildDavReverseQuery({
        rxcui:reverseRx,kind,review:req.query?.review,
        page:req.query?.page,pageSize:req.query?.pageSize
      });
      const [counts,products]=await Promise.all([
        sql.query(reverse.countSql,reverse.countParams),
        sql.query(reverse.rowsSql,reverse.params)
      ]);
      const totalRows=Number(counts[0]?.total_rows||0);
      const totalPages=Math.ceil(totalRows/reverse.pageSize);
      return res.status(200).json({
        mode:'database',scope:'rxnorm_to_dav',concept,relationKind:kind,
        review:reverse.review,page:reverse.page,pageSize:reverse.pageSize,
        totalRows,totalPages,hasNextPage:reverse.page<totalPages,products,
        clinicalNote:kind==='ingredient'
          ?'Chỉ có bằng chứng ứng viên thành phần hoạt chất. Không suy ra rằng mọi sản phẩm có cùng hàm lượng, dạng bào chế hay được duyệt mapping thuốc.'
          :'ACCEPTED_SCD biểu thị mapping đã được chấp nhận trong Gold; CANDIDATE_SCD chưa được thẩm định. Không tự suy ra tương đương điều trị.'
      });
    }
    const query=buildConceptQuery(req.query||{});
    if(!query)return res.status(400).json({error:'MISSING_QUERY',notice:'Truyền q hoặc dav_row_id'});
    const [counts,items]=await Promise.all([
      sql.query(query.countSql,query.countParams),
      sql.query(query.rowsSql,query.params)
    ]);
    const totalRows=Number(counts[0]?.total_rows||0),totalPages=Math.ceil(totalRows/query.pageSize);
    return res.status(200).json({
      mode:'database',scope:'rxnorm_terminology',q:String(req.query.q).trim(),
      page:query.page,pageSize:query.pageSize,totalRows,totalPages,
      hasNextPage:query.page<totalPages,items,
      clinicalNote:'Tìm thuật ngữ RxNorm không đồng nghĩa với xác nhận cùng thuốc/sản phẩm DAV.'
    });
  } catch(e) {
    console.error('RxNorm lookup failed',e?.name||'unknown',e?.code||'');
    return res.status(503).json({mode:'unavailable',reason:'NEON_QUERY_FAILED'});
  }
}
module.exports=handler;
module.exports.buildConceptQuery=buildConceptQuery;

module.exports.buildDavReverseQuery=buildDavReverseQuery;
