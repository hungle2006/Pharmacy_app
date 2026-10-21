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
