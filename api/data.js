'use strict';
const { neon } = require('@neondatabase/serverless');

// Bounded page size, never a global truncation of the Gold data.
const pageNumber = value => {
  const n=Number(value);
  return Number.isSafeInteger(n)&&n>0 ? Math.min(n,100000) : 1;
};
const pageSizeNumber = value => {
  const n=Number(value);
  return Number.isSafeInteger(n)&&n>0 ? Math.min(n,200) : 100;
};
const escapeLike = value => String(value).replace(/[\\%_]/g,'\\$&');
const money = value => value===null||value===undefined||value==='' ? null :
  Number.isFinite(Number(value)) ? Number(value) : null;

// One result row = one DAV product x price observation, including unpriced products.
function buildQuery(query={}) {
  const page=pageNumber(query.page), pageSize=pageSizeNumber(query.pageSize);
  const params=[];
  const bind=v=>{params.push(v);return '$'+params.length;};
  const clauses=[];
  if(typeof query.q==='string'&&query.q.trim()) {
    const param=bind('%'+escapeLike(query.q.trim().slice(0,160))+'%');
    clauses.push('('+['d.drug_name','d.active_ingredient_raw',
      'd.registration_number','d.manufacturer'].map(x=>x+' ILIKE '+param).join(' OR ')+')');
  }
  for(const [name,expr] of [
    ['ingredient','d.active_ingredient_raw'],['country','d.country'],
    ['kind','p.price_type'],['unit',"COALESCE(NULLIF(p.unit,''),NULLIF(d.unit,''))"]
  ]) {
    if(typeof query[name]==='string'&&query[name].trim())
      clauses.push(expr+' = '+bind(query[name].trim().slice(0,160)));
  }
  if(query.currentOnly==='true') clauses.push("d.source = 'SILVER_R2'");
  const productMode=query.mode==='products';
  const from=[
    'FROM public.dav_product d',
    'LEFT JOIN public.price_record p ON p.dav_row_id=d.dav_row_id',
    clauses.length?'WHERE '+clauses.join(' AND '):''
  ].join(' ');
  const countSql=(productMode?'SELECT COUNT(DISTINCT d.dav_row_id)::bigint AS total_rows ':'SELECT COUNT(*)::bigint AS total_rows ')+from;
  const countParams=params.slice();
  const limit=bind(pageSize),offset=bind((page-1)*pageSize);
  const rowsSql=[
    (productMode?'SELECT DISTINCT ON (d.dav_row_id) d.dav_row_id AS id, d.drug_name,':'SELECT d.dav_row_id AS id, d.drug_name,'),
    "NULLIF(d.active_ingredient_raw,'') AS ingredient,",
    "NULLIF(d.strength_raw,'') AS strength,",
    "NULLIF(d.dosage_form_raw,'') AS dosage_form,",
    "NULLIF(d.manufacturer,'') AS manufacturer,",
    "NULLIF(d.country,'') AS country,",
    'NULL::text AS therapeutic_group,',
    'd.registration_number AS registration_no, d.source AS product_source,',
    'd.catalog_duplicate_status, d.catalog_equivalent_to, p.price_id,',
    "CASE WHEN p.price_vnd >= 0 AND (p.currency='VND' OR p.currency IS NULL OR p.currency='')",
    'THEN p.price_vnd ELSE NULL END AS price_vnd,',
    "NULLIF(p.price_type,'') AS price_type, p.declaration_date AS snapshot_date,",
    "COALESCE(NULLIF(p.unit,''),NULLIF(d.unit,'')) AS unit,",
    "COALESCE(NULLIF(p.package,''),NULLIF(d.package,'')) AS package",
    from,
    'ORDER BY d.dav_row_id ASC, p.declaration_date DESC NULLS LAST, p.price_id ASC NULLS LAST',
    'LIMIT '+limit+' OFFSET '+offset
  ].join(' ');
  return {page,pageSize,productMode,countSql,countParams,rowsSql,params,offset:(page-1)*pageSize};
}

async function handler(req,res) {
  res.setHeader('Cache-Control','private, no-store');
  if(req.method!=='GET')return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
  if(!process.env.DATABASE_URL)return res.status(503).json({
    mode:'unavailable',reason:'DATABASE_URL_MISSING',notice:'Chưa cấu hình kết nối Neon Gold'
  });
  try {
    const query=buildQuery(req.query||{});
    const sql=neon(process.env.DATABASE_URL);
    const [counts,rows]=await Promise.all([
      sql.query(query.countSql,query.countParams),
      sql.query(query.rowsSql,query.params)
    ]);
    const totalRows=Number(counts[0]?.total_rows||0);
    const totalPages=Math.ceil(totalRows/query.pageSize);
    const records=rows.map(row=>({
      ...row,
      price_vnd:money(row.price_vnd),
      snapshot_date:row.snapshot_date==null?null:String(row.snapshot_date).slice(0,10)
    }));
    return res.status(200).json({
      mode:'database',source:'Neon Gold · dav_product × price_record',
      scope:'full_gold_paginated',sampled:false,grain:query.productMode?'product':'price_observation',
      page:query.page,pageSize:query.pageSize,totalRows,totalPages,
      hasNextPage:query.page<totalPages,
      hasPreviousPage:query.page>1&&totalPages>0,
      priced:records.some(x=>x.price_vnd!==null),records,
      notice:query.productMode?'Danh mục theo từng mã sản phẩm DAV; hiển thị giá quan sát mới nhất nếu có. Bản ghi nghi trùng được gắn cờ, không tự xóa.':'Neon Gold phân trang trên toàn bộ dữ liệu, không giới hạn tổng 2.000 dòng. Mỗi dòng là một quan sát thuốc × giá; sản phẩm nghi trùng được giữ và gắn cờ.'
    });
  } catch(e) {
    console.error('PharmaBiz Gold pagination failed',e?.name||'unknown',e?.code||'');
    return res.status(503).json({mode:'unavailable',reason:'NEON_QUERY_FAILED',
      notice:'Không truy vấn được Gold. Kiểm tra kết nối Neon hoặc thử lại.'});
  }
}
module.exports=handler;
module.exports.buildQuery=buildQuery;
