const { neon } = require('@neondatabase/serverless');
const TABLES=['dav_product','price_record','dav_rxnorm_mapping','disease','medi_relation','rxnorm_concept','rxnorm_scd','rxnorm_scd_component'];
const qi=x=>'"'+String(x).replace(/"/g,'""')+'"';
const choice=(columns,arr)=>Array.from(arr).find(c=>columns.has(c))||null;
const safeNumber=n=>(n===null||n===undefined||n==='')?null:(Number.isFinite(Number(n))?Number(n):null);
module.exports=async function handler(req,res){
 res.setHeader('Cache-Control','private, no-store');
 if(req.method!=='GET')return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
 if(!process.env.DATABASE_URL)return res.status(200).json({mode:'demo',reason:'DATABASE_URL_MISSING',notice:'Chưa cấu hình DATABASE_URL trên Vercel'});
 try{
  const sql=neon(process.env.DATABASE_URL);
  const schema=await sql`SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('dav_product','price_record','analytics_drug_prices')`;
  const columns=new Map();for(const c of schema){if(!columns.has(c.table_name))columns.set(c.table_name,new Map());columns.get(c.table_name).set(c.column_name,c.data_type);}
  const build=(prefix,cols,keys,alias,cast=false)=>{const c=choice(cols,new Set(keys));return c?(cast?`NULLIF(TRIM(${prefix}.${qi(c)}::text),'') AS ${qi(alias)}`:`${prefix}.${qi(c)} AS ${qi(alias)}`):`NULL AS ${qi(alias)}`};
  if(columns.has('analytics_drug_prices')){
   const c=columns.get('analytics_drug_prices');
   const price=choice(c,new Set(['price_vnd']));
   if(price){
    const f=['id','drug_name','ingredient','strength','dosage_form','manufacturer','country','price_type','therapeutic_group','snapshot_date','registration_no'].map(k=>build('d',c,[k],k,k!=='snapshot_date'));
    const query=`SELECT ${f.join(',')}, d.${qi(price)} AS price_vnd FROM public.analytics_drug_prices d WHERE d.${qi(price)} IS NOT NULL ORDER BY d.${qi(price)} DESC NULLS LAST LIMIT 2000`;
    const items=await sql.query(query);
    return res.status(200).json({mode:'database',source:'analytics_drug_prices',sampled:true,sampleLimit:2000,records:items.map(r=>({...r,price_vnd:safeNumber(r.price_vnd),snapshot_date:r.snapshot_date?String(r.snapshot_date).slice(0,10):''})),notice:'Dữ liệu thật từ analytics_drug_prices — số liệu trên dashboard chỉ phản ánh mẫu tối đa 2.000 dòng, không phải toàn bộ thị trường.'});
   }
  }
  const dcols=columns.get('dav_product');
  if(!dcols)return res.status(200).json({mode:'demo',reason:'DAV_TABLE_NOT_FOUND',notice:'Không tìm thấy bảng public.dav_product'});
  const pcols=columns.get('price_record');
  const fields=[
   build('d',dcols,['dav_row_id','id','product_id'],'id',true),
   build('d',dcols,['drug_name','ten_thuoc','name'],'drug_name',true),
   build('d',dcols,['active_ingredient_raw','active_ingredient','ingredient','ingredient_name'],'ingredient',true),
   build('d',dcols,['strength_raw','strength','strength_text'],'strength',true),
   build('d',dcols,['dosage_form_raw','dosage_form','form'],'dosage_form',true),
   build('d',dcols,['manufacturer_raw','manufacturer_name','manufacturer','producer_name'],'manufacturer',true),
   build('d',dcols,['manufacturing_country','country_raw','country','country_of_origin'],'country',true),
   build('d',dcols,['therapeutic_group','atc_group'],'therapeutic_group',true),
   build('d',dcols,['registration_number','registration_no','so_dang_ky'],'registration_no',true)
  ];
  const priceCol=pcols&&choice(pcols,new Set(['unit_price_vnd','price_vnd','winning_price','bid_price','price','unit_price','declared_price','price_amount']));
  const typeCol=pcols&&choice(pcols,new Set(['price_type','source_type','price_source','type']));
  const dateCol=pcols&&choice(pcols,new Set(['declaration_date','price_date','effective_date','created_at','updated_at','recorded_at','date']));
  const dkey=choice(dcols,new Set(['dav_row_id','product_id','id']));
  const pkey=pcols&&choice(pcols,new Set(['dav_row_id','product_id','dav_product_id']));
  let rows=[],source='dav_product',priced=false;
  if(priceCol&&dkey&&pkey&&['numeric','integer','bigint','double precision','real','smallint','decimal'].includes(pcols.get(priceCol))){
   const query=`SELECT ${fields.join(',')}, p.${qi(priceCol)} AS price_vnd, ${typeCol?`p.${qi(typeCol)}::text`:"'Chưa rõ loại giá'"} AS price_type, ${dateCol?`p.${qi(dateCol)}::text`:"NULL::text"} AS snapshot_date FROM public.price_record p JOIN public.dav_product d ON p.${qi(pkey)}::text=d.${qi(dkey)}::text WHERE p.${qi(priceCol)} IS NOT NULL AND p.${qi(priceCol)}>=0 LIMIT 2000`;
   try{rows=await sql.query(query);priced=true;source='dav_product × price_record';}catch(e){console.error('Joined price sampling unavailable',e.name);}
  }
  if(!rows.length){
    const query=`SELECT ${fields.join(',')}, NULL::numeric AS price_vnd, 'Chưa có giá chuẩn hóa'::text AS price_type, NULL::text AS snapshot_date FROM public.dav_product d LIMIT 2000`;
    rows=await sql.query(query);
    source='dav_product';priced=false;
  }
  const records=rows.map((x,i)=>({...x,id:x.id||String(i),price_vnd:safeNumber(x.price_vnd),snapshot_date:x.snapshot_date?String(x.snapshot_date).slice(0,10):''}));
  return res.status(200).json({mode:'database',source,sampled:true,sampleLimit:2000,priced,records,notice:priced?'Dữ liệu Neon thật: mẫu tối đa 2.000 bản ghi; không suy ra thị phần hay doanh thu.':'Đã đọc danh mục DAV từ Neon nhưng chưa ghép được giá số hợp lệ trong price_record. Giá và biểu đồ giá sẽ để trống.'});
 }catch(e){console.error('PharmaBiz datasource failure:',e instanceof Error?e.name:'unknown');return res.status(503).json({mode:'unavailable',reason:'NEON_QUERY_FAILED',notice:'Không đọc được Neon. Kiểm tra quyền SELECT, DATABASE_URL và cấu trúc bảng.'});}
};
