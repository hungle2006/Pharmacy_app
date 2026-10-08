const {neon}=require('@neondatabase/serverless');
const tables=['dav_product','price_record','dav_rxnorm_mapping','disease','medi_relation','rxnorm_concept','rxnorm_scd','rxnorm_scd_component'];
module.exports=async(req,res)=>{
 res.setHeader('Cache-Control','private, no-store');
 if(req.method!=='GET')return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
 if(!process.env.DATABASE_URL)return res.status(200).json({mode:'demo',reason:'DATABASE_URL_MISSING',tables:[],lineage:[]});
 try{
   const sql=neon(process.env.DATABASE_URL);
   const cols=await sql`SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('dav_product','price_record','dav_rxnorm_mapping','disease','medi_relation','rxnorm_concept','rxnorm_scd','rxnorm_scd_component') ORDER BY table_name,ordinal_position`;
   const est=await sql`SELECT c.relname::text AS name,c.reltuples::bigint AS approx_rows FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p') AND c.relname IN ('dav_product','price_record','dav_rxnorm_mapping','disease','medi_relation','rxnorm_concept','rxnorm_scd','rxnorm_scd_component')`;
   const e=Object.fromEntries(est.map(x=>[x.name,x.approx_rows===null?null:Number(x.approx_rows)]));
   const result=tables.map(t=>({name:t,available:cols.some(c=>c.table_name===t),estimatedRows:(e[t]??-1)>=0?e[t]:null,columns:cols.filter(c=>c.table_name===t).map(c=>({name:c.column_name,type:c.data_type}))})); 
   return res.status(200).json({mode:'database',database:'neondb',schema:'public',tables:result,countType:'estimated_pg_class_reltuples',notice:'Số dòng ước lượng của PostgreSQL, không phải COUNT(*) chính xác.',refreshedAt:new Date().toISOString()});
 }catch(e){console.error('Schema diagnostics unavailable',e instanceof Error?e.name:'unknown');return res.status(503).json({mode:'unavailable',reason:'NEON_SCHEMA_QUERY_FAILED'});}
}