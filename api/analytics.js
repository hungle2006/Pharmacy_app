const { neon } = require('@neondatabase/serverless');
const number = v => Number.isFinite(Number(v)) ? Math.max(1, Math.min(100000, Math.floor(Number(v) || 1))) : 1;
function buildQuery(query = {}) {
  const params = [], clauses = [];
  const bind = value => { params.push(String(value).slice(0, 200)); return '$' + params.length; };
  if (query.q) {
    const p = bind('%' + String(query.q).replace(/[\\%_]/g, '\\$&') + '%');
    clauses.push(`(d.drug_name ILIKE ${p} OR d.active_ingredient_raw ILIKE ${p} OR d.manufacturer ILIKE ${p} OR d.registration_number ILIKE ${p})`);
  }
  for (const [key, column] of [['ingredient','d.active_ingredient_raw'],['country','d.country'],['kind','p.price_type'],['unit',"COALESCE(NULLIF(p.unit,''),NULLIF(d.unit,''))"]]) {
    if (query[key]) clauses.push(`${column} = ${bind(query[key])}`);
  }
  const page = number(query.page), offset = (page - 1) * 12;
  const text = `WITH base AS MATERIALIZED (
    SELECT d.dav_row_id AS id, d.registration_number AS registration_no, d.drug_name,
      NULLIF(d.active_ingredient_raw,'') AS ingredient, NULLIF(d.strength_raw,'') AS strength,
      NULLIF(d.dosage_form_raw,'') AS dosage_form, NULLIF(d.manufacturer,'') AS manufacturer,
      NULLIF(d.country,'') AS country, p.price_id,
      CASE WHEN p.price_vnd >= 0 AND (p.currency = 'VND' OR p.currency IS NULL OR p.currency = '') THEN p.price_vnd ELSE NULL END AS price_vnd,
      NULLIF(p.price_type,'') AS price_type, p.declaration_date AS snapshot_date,
      COALESCE(NULLIF(p.unit,''),NULLIF(d.unit,'')) AS unit, COALESCE(NULLIF(p.package,''),NULLIF(d.package,'')) AS package
    FROM public.dav_product d LEFT JOIN public.price_record p ON p.dav_row_id = d.dav_row_id
    ${clauses.length ? 'WHERE ' + clauses.join(' AND ') : ''}
  ), unique_products AS (SELECT DISTINCT ON (id) * FROM base ORDER BY id, snapshot_date DESC NULLS LAST, price_id),
  summary AS (SELECT COUNT(*) AS observations, COUNT(DISTINCT id) AS products,
    COUNT(DISTINCT ingredient) AS ingredients, COUNT(DISTINCT manufacturer) AS manufacturers,
    COUNT(DISTINCT country) AS countries, COUNT(price_vnd) AS priced,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY price_vnd) AS median,
    percentile_cont(0.1) WITHIN GROUP (ORDER BY price_vnd) AS p10,
    percentile_cont(0.9) WITHIN GROUP (ORDER BY price_vnd) AS p90,
    MIN(snapshot_date) AS date_from, MAX(snapshot_date) AS date_to FROM base),
  countries AS (SELECT COALESCE(country,'Chưa xác định') AS name, COUNT(*) AS value FROM unique_products GROUP BY country ORDER BY value DESC),
  ingredients AS (SELECT ingredient AS name, COUNT(*) AS value, COUNT(DISTINCT manufacturer) AS makers FROM unique_products WHERE ingredient IS NOT NULL GROUP BY ingredient ORDER BY value DESC,ingredient LIMIT 8),
  manufacturers AS (SELECT manufacturer AS name, COUNT(*) AS value, COUNT(DISTINCT ingredient) AS ingredients FROM unique_products WHERE manufacturer IS NOT NULL GROUP BY manufacturer ORDER BY value DESC,manufacturer LIMIT 10),
  forms AS (SELECT COALESCE(dosage_form,'Chưa xác định') AS name, COUNT(*) AS value FROM unique_products GROUP BY dosage_form ORDER BY value DESC),
  timeline AS (SELECT to_char(snapshot_date,'YYYY-MM') AS name, COUNT(price_vnd) AS value,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY price_vnd) AS median FROM base WHERE snapshot_date IS NOT NULL GROUP BY 1 ORDER BY 1),
  bins AS (SELECT CASE WHEN price_vnd<1000 THEN 0 WHEN price_vnd<5000 THEN 1 WHEN price_vnd<10000 THEN 2 WHEN price_vnd<50000 THEN 3 WHEN price_vnd<100000 THEN 4 ELSE 5 END AS bucket,COUNT(*) AS value FROM base WHERE price_vnd IS NOT NULL GROUP BY 1 ORDER BY 1),
  comparable AS (SELECT ingredient,strength,dosage_form,unit,price_type,COUNT(*) AS observations,COUNT(DISTINCT id) AS products,COUNT(DISTINCT manufacturer) AS makers,
    percentile_cont(0.1) WITHIN GROUP (ORDER BY price_vnd) AS p10,percentile_cont(0.5) WITHIN GROUP (ORDER BY price_vnd) AS median,percentile_cont(0.9) WITHIN GROUP (ORDER BY price_vnd) AS p90
    FROM base WHERE price_vnd IS NOT NULL AND ingredient IS NOT NULL AND strength IS NOT NULL AND dosage_form IS NOT NULL AND unit IS NOT NULL AND price_type IS NOT NULL
    GROUP BY ingredient,strength,dosage_form,unit,price_type HAVING COUNT(DISTINCT id)>=2 ORDER BY COUNT(*) DESC LIMIT 15),
  rows AS (SELECT * FROM base ORDER BY drug_name NULLS LAST,id,snapshot_date DESC NULLS LAST,price_id LIMIT 12 OFFSET ${offset}),
  quality AS (SELECT COUNT(*) AS total,COUNT(drug_name) FILTER (WHERE drug_name<>'') AS drug_name,COUNT(ingredient) AS ingredient,COUNT(strength) AS strength,COUNT(dosage_form) AS dosage_form,COUNT(manufacturer) AS manufacturer,COUNT(country) AS country,COUNT(unit) AS unit FROM unique_products)
  SELECT row_to_json(summary) AS summary,(SELECT row_to_json(quality) FROM quality) AS quality,
    COALESCE((SELECT json_agg(c) FROM countries AS c),'[]') AS countries,
    COALESCE((SELECT json_agg(c) FROM ingredients AS c),'[]') AS ingredients,
    COALESCE((SELECT json_agg(c) FROM manufacturers AS c),'[]') AS manufacturers,
    COALESCE((SELECT json_agg(c) FROM forms AS c),'[]') AS forms,
    COALESCE((SELECT json_agg(c) FROM timeline AS c),'[]') AS timeline,
    COALESCE((SELECT json_agg(c) FROM bins AS c),'[]') AS bins,
    COALESCE((SELECT json_agg(c) FROM comparable AS c),'[]') AS comparable,
    COALESCE((SELECT json_agg(c) FROM rows AS c),'[]') AS records FROM summary`;
  return { text, params, page };
}
async function handler(req, res) {
  res.setHeader('Cache-Control','no-store');
  if (req.method !== 'GET') return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
  if (!process.env.DATABASE_URL) return res.status(503).json({mode:'unavailable',reason:'DATABASE_URL_MISSING',notice:'Nguồn dữ liệu chưa được kết nối.'});
  try {
    const sql = neon(process.env.DATABASE_URL), query = buildQuery(req.query);
    const [result, options, mapping] = await Promise.all([
      sql.query(query.text, query.params),
      sql.query(`SELECT json_build_object(
        'ingredient',(SELECT COALESCE(json_agg(name),'[]') FROM (SELECT DISTINCT active_ingredient_raw AS name FROM public.dav_product WHERE active_ingredient_raw IS NOT NULL AND active_ingredient_raw<>'' ORDER BY name LIMIT 5000) a),
        'country',(SELECT COALESCE(json_agg(name),'[]') FROM (SELECT DISTINCT country AS name FROM public.dav_product WHERE country IS NOT NULL AND country<>'' ORDER BY name) a),
        'kind',(SELECT COALESCE(json_agg(name),'[]') FROM (SELECT DISTINCT price_type AS name FROM public.price_record WHERE price_type IS NOT NULL AND price_type<>'' ORDER BY name) a),
        'unit',(SELECT COALESCE(json_agg(name),'[]') FROM (SELECT DISTINCT COALESCE(NULLIF(p.unit,''),NULLIF(d.unit,'')) AS name FROM public.dav_product d LEFT JOIN public.price_record p ON p.dav_row_id=d.dav_row_id) a WHERE name IS NOT NULL)
      ) AS options`),
      sql.query(`SELECT COUNT(*) AS total,COUNT(*) FILTER (WHERE accepted_for_serving=1) AS accepted,
        COUNT(*) FILTER (WHERE review_required=1) AS review,COUNT(*) FILTER (WHERE selected_scd_fk_valid=1) AS valid_fk,
        (SELECT COUNT(*) FROM public.disease) AS diseases,(SELECT COUNT(*) FROM public.medi_relation) AS relations,
        (SELECT COUNT(*) FROM public.rxnorm_concept) AS concepts,
        (SELECT COALESCE(json_agg(s),'[]') FROM (SELECT COALESCE(mapping_status,'Chưa xác định') AS name,COUNT(*) AS value FROM public.dav_rxnorm_mapping GROUP BY 1 ORDER BY 2 DESC) s) AS statuses
        FROM public.dav_rxnorm_mapping`).catch(() => [{ unavailable:true }])
    ]);
    return res.status(200).json({mode:'database',scope:'full_database_filtered',source:'Neon PostgreSQL · DAV × price_record',refreshedAt:new Date().toISOString(),page:query.page,pageSize:12,...result[0],options:options[0].options,mapping:mapping[0],notice:'KPI và biểu đồ được tính bằng SQL trên toàn bộ dữ liệu trong phạm vi bộ lọc. Giá quan sát cần được xem cùng đơn vị, loại giá và cấu hình sản phẩm.'});
  } catch (e) {
    console.error('Analytics query failed', e.name, e.code || '');
    return res.status(503).json({mode:'unavailable',reason:'NEON_QUERY_FAILED',notice:'Không thể tải dữ liệu. Vui lòng thử lại hoặc kiểm tra kết nối nguồn.'});
  }
}
module.exports = handler;
module.exports.buildQuery = buildQuery;
