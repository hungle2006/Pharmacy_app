'use strict';
const {neon}=require('@neondatabase/serverless');
// Public aggregates only. Different grains remain separate; no record writes.
const diseaseQuery=`SELECT COUNT(*) AS total,
 COUNT(*) FILTER (WHERE NULLIF(TRIM(disease_name_vi),'') IS NOT NULL) AS named_vi,
 COALESCE((SELECT json_agg(c ORDER BY c.value DESC,c.name) FROM
 (SELECT COALESCE(NULLIF(TRIM(chapter_code),''),'Chưa phân chương') AS name,COUNT(*) AS value
 FROM public.disease GROUP BY 1) c),'[]') AS chapters FROM public.disease`;
const mediQuery=`SELECT COUNT(*) AS total,COUNT(DISTINCT rxcui) AS concepts,
 COUNT(*) FILTER (WHERE code_system='ICD10CM') AS icd10cm,
 COUNT(*) FILTER (WHERE code_system='ICD10CM' AND disease_icd_code IS NOT NULL) AS with_icd_link,
 COUNT(*) FILTER (WHERE code_system='ICD10CM' AND disease_icd_code IS NOT NULL AND icd_match_status='EXACT_ICD10_CODE') AS exact_icd_link,
 COUNT(*) FILTER (WHERE disease_icd_code IS NOT NULL AND code_system='ICD10CM'
 AND icd_match_status='EXACT_ICD10_CODE' AND rxnorm_match_status='FOUND_IN_RXNORM_SNAPSHOT') AS eligible,
 COALESCE((SELECT json_agg(c ORDER BY c.value DESC,c.name) FROM
 (SELECT COALESCE(NULLIF(TRIM(code_system),''),'Chưa xác định') AS name,COUNT(*) AS value
 FROM public.medi_relation GROUP BY 1) c),'[]') AS systems FROM public.medi_relation`;
async function handler(req,res){
 res.setHeader('Cache-Control','public, max-age=0, s-maxage=120');
 res.setHeader('X-Content-Type-Options','nosniff');
 if(req.method!=='GET')return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
 if(!process.env.DATABASE_URL)return res.status(503).json({error:'SOURCE_UNAVAILABLE'});
 try{
  const sql=neon(process.env.DATABASE_URL);
  const results=await Promise.allSettled([sql.query(diseaseQuery,[]),sql.query(mediQuery,[])]);
  const [disease,medi]=results.map(r=>r.status==='fulfilled'?r.value[0]:null);
  return res.status(disease||medi?200:503).json({mode:disease||medi?'database':'unavailable',disease,medi,
   refreshedAt:new Date().toISOString(),source:'Neon Gold · disease / medi_relation',countType:'exact_count',
   grains:{disease:'Một dòng mã ICD trong Gold',medi:'Một dòng quan hệ MEDI; không phải số bệnh nhân hoặc chỉ định đã xác minh'}});
 }catch(error){console.error('Story aggregates unavailable',error?.name||'error');return res.status(503).json({error:'SOURCE_UNAVAILABLE'});}
}
module.exports=handler;module.exports.diseaseQuery=diseaseQuery;module.exports.mediQuery=mediQuery;
