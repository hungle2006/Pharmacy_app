const { neon } = require('@neondatabase/serverless');
module.exports = async function handler(req,res) {
  res.setHeader('Cache-Control','no-store');
  if(req.method!=='GET') return res.status(405).json({error:'Method not allowed'});
  if(!process.env.DATABASE_URL) return res.status(200).json({mode:'demo',records:[],notice:'No DATABASE_URL configured'});
  try {
    const sql=neon(process.env.DATABASE_URL);
    // Create a read-only analytics_drug_prices VIEW, not unrestricted access to raw source tables.
    const rows=await sql`SELECT id,drug_name,ingredient,strength,dosage_form,manufacturer,country,price_vnd,price_type,therapeutic_group,snapshot_date,registration_no FROM analytics_drug_prices WHERE price_vnd IS NOT NULL AND price_vnd >= 0 ORDER BY snapshot_date DESC NULLS LAST LIMIT 5001`;
    const truncated=rows.length>5000;
    return res.status(200).json({mode:'database',records:rows.slice(0,5000).map(r=>({...r,price_vnd:Number(r.price_vnd),snapshot_date:r.snapshot_date?String(r.snapshot_date).slice(0,10):''})),notice:truncated?'Đang hiển thị tối đa 5.000 bản ghi, các KPI chưa đại diện toàn bộ database.':'Đọc dữ liệu từ PostgreSQL / Neon.'});
  } catch(e) {
    console.error('Database analytics query failed',e instanceof Error?e.name:'unknown');
    return res.status(200).json({mode:'demo',records:[],notice:'Analytics database view unavailable'});
  }
}