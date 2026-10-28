'use strict';
const {neon}=require('@neondatabase/serverless');
const catalog={
 dav_product:{label:'Danh mục thuốc DAV',grain:'Một hồ sơ sản phẩm DAV',question:'Danh mục đang có những gì, và còn thiếu gì để so sánh thuốc?',purpose:'Là điểm bắt đầu của tra cứu sản phẩm và phân tích nguồn cung.',category:'country',secondary:'dosage_form_raw',measure:'drug_name',next:'price_record',fields:['drug_name','active_ingredient_raw','strength_raw','dosage_form_raw','manufacturer','country','unit','registration_number']},
 price_record:{label:'Quan sát giá',grain:'Một lần ghi nhận giá của một sản phẩm',question:'Giá được ghi nhận ở những mức nào, trong đơn vị và thời điểm nào?',purpose:'Một sản phẩm có thể có nhiều quan sát giá; số dòng không phải số thuốc.',category:'price_type',secondary:'unit',measure:'price_vnd',date:'declaration_date',next:'dav_rxnorm_mapping'},
 disease:{label:'Danh mục bệnh ICD-10',grain:'Một mã bệnh trong danh mục Gold',question:'Danh mục mã bệnh được phân chương và mô tả đầy đủ đến đâu?',purpose:'Giúp xác định mã khi tìm kiếm tên bệnh, không phản ánh số ca mắc bệnh.',category:'chapter_code',secondary:'normalization_status',measure:'disease_name_vi',next:'medi_relation'},
 medi_relation:{label:'Quan hệ MEDI',grain:'Một dòng quan hệ thuốc–mã bệnh',question:'Các quan hệ dùng hệ mã nào và đã nối được tới đâu?',purpose:'Đọc bằng chứng liên quan; không đồng nhất quan hệ dữ liệu với chỉ định đã xác minh.',category:'code_system',secondary:'icd_match_status',next:'rxnorm_concept'},
 rxnorm_concept:{label:'Khái niệm RxNorm · Gold',grain:'Một mã RxCUI trong bảng khái niệm Gold',question:'Các khái niệm thuốc trong Gold được biểu diễn như thế nào?',purpose:'Mã RxCUI là định danh; không tính trung bình mã. Bảng Gold có đơn vị khác dòng thuật ngữ Silver.',category:'canonical_tty',secondary:'canonical_sab',measure:'canonical_name',next:'rxnorm_scd'},
 rxnorm_scd:{label:'Thuốc lâm sàng SCD',grain:'Một khái niệm thuốc lâm sàng chuẩn',question:'Các cấu hình thuốc chuẩn đã được mô tả đầy đủ chưa?',purpose:'Làm đối tượng đối chiếu cấu hình thuốc; tên gần nhau chưa đủ để xác nhận tương đương.',category:'dose_form_name',secondary:'component_status',measure:'scd_name',next:'rxnorm_scd_component'},
 rxnorm_scd_component:{label:'Thành phần SCD',grain:'Một dòng thành phần của SCD',question:'Mỗi cấu hình thuốc được mô tả bằng những thành phần nào?',purpose:'Một SCD có thể có nhiều thành phần; không đếm các dòng thành phần như số thuốc.',category:'relation_status',secondary:'ingredient_tty',measure:'ingredient_name',next:'dav_rxnorm_mapping'},
 dav_rxnorm_mapping:{label:'Mapping DAV ↔ RxNorm',grain:'Một dòng liên kết sản phẩm DAV',question:'Những liên kết nào đã được chấp nhận và những gì còn cần rà soát?',purpose:'Giữ riêng trạng thái mapping và các cờ kỹ thuật; khóa hợp lệ chưa chứng minh tương đương điều trị.',category:'mapping_status',secondary:'review_reason',next:'dav_rxnorm_evidence'},
 dav_rxnorm_evidence:{label:'Bằng chứng mapping',grain:'Một dòng bằng chứng đối chiếu DAV–RxNorm',question:'Các ứng viên mapping đang có những loại bằng chứng nào?',purpose:'Bằng chứng giúp kiểm tra tại sao có một liên kết, không tự biến ứng viên thành kết luận lâm sàng.',category:'evidence_status',secondary:'match_method',next:'dav_product'}
};
function quoteId(v){if(!/^[a-z_][a-z0-9_]*$/.test(v))throw Error('INVALID_IDENTIFIER');return '"'+v+'"';}
function buildProfileQuery(name,columns){
 if(!Object.hasOwn(catalog,name))throw Error('INVALID_TABLE');const cfg=catalog[name];
 const cols=columns.filter(c=>/^[a-z_][a-z0-9_]*$/.test(c.name));const names=new Set(cols.map(c=>c.name)),table='public.'+quoteId(name);
 const text=c=>'NULLIF(BTRIM('+quoteId(c)+'::text),\'\')';
 const agg=cols.flatMap((c,i)=>['COUNT(*) FILTER (WHERE '+text(c.name)+' IS NULL) AS m'+i,'COUNT(DISTINCT '+text(c.name)+') AS u'+i]);
 const measure=names.has(cfg.measure)?cfg.measure:null;
 const numeric=measure?(name==='price_record'?`CASE WHEN price_vnd>=0 AND price_vnd::text NOT IN ('NaN','Infinity','-Infinity') ${names.has('currency')?"AND (currency='VND' OR NULLIF(TRIM(currency),'') IS NULL)":''} THEN price_vnd::double precision END`:'char_length('+text(measure)+')::double precision'):null;
 if(numeric)agg.push('COUNT('+numeric+') AS n','AVG('+numeric+') AS mean','STDDEV_POP('+numeric+') AS sd','MIN('+numeric+') AS min','MAX('+numeric+') AS max',...[.1,.25,.5,.75,.9].map((p,i)=>'percentile_cont('+p+') WITHIN GROUP(ORDER BY '+numeric+') AS p'+i));
 const ctes=['metrics AS (SELECT COUNT(*) AS total'+(agg.length?','+agg.join(','):'')+' FROM '+table+')'];
 const lists=[];
 for(const [key,column] of [['distribution',cfg.category],['secondary',cfg.secondary]]){
  if(!names.has(column)){lists.push("'[]'::json AS "+key);continue;}
  ctes.push(key+" AS (SELECT COALESCE("+text(column)+",'Chưa có thông tin') AS name,COUNT(*) AS value FROM "+table+' GROUP BY 1)');
  lists.push("COALESCE((SELECT json_agg(g ORDER BY g.value DESC,g.name) FROM "+key+" g),'[]') AS "+key);
 }
 if(names.has(cfg.category)&&names.has(cfg.secondary)){
  const cat="COALESCE("+text(cfg.category)+",'Chưa có thông tin')",sec="COALESCE("+text(cfg.secondary)+",'Chưa có thông tin')";
  ctes.push('cross_distribution AS (SELECT CASE WHEN '+cat+"='Chưa có thông tin' OR "+cat+" IN (SELECT name FROM distribution ORDER BY value DESC,name LIMIT 5) THEN "+cat+" ELSE 'Các nhóm khác' END AS \"row\", CASE WHEN "+sec+"='Chưa có thông tin' OR "+sec+" IN (SELECT name FROM secondary ORDER BY value DESC,name LIMIT 5) THEN "+sec+" ELSE 'Các nhóm khác' END AS \"column\",COUNT(*) AS value FROM "+table+' GROUP BY 1,2)');
  lists.push("COALESCE((SELECT json_agg(g ORDER BY g.value DESC,g.\"row\",g.\"column\") FROM cross_distribution g),'[]') AS cross_distribution");
 }
 if(numeric){const bounds=name==='price_record'?[1000,5000,10000,50000,100000]:[20,40,60,100,200];
  ctes.push('bins AS (SELECT CASE '+bounds.map((b,i)=>'WHEN ('+numeric+')<'+b+' THEN '+i+' ').join('')+'ELSE 5 END AS bucket,COUNT(*) AS value FROM '+table+' WHERE ('+numeric+') IS NOT NULL GROUP BY 1)');
  lists.push("COALESCE((SELECT json_agg(b ORDER BY b.bucket) FROM bins b),'[]') AS bins");
 }
 if(names.has(cfg.date)){ctes.push('timeline AS (SELECT to_char('+quoteId(cfg.date)+",'YYYY-MM') AS name,COUNT(*) AS value FROM "+table+' WHERE '+quoteId(cfg.date)+' IS NOT NULL GROUP BY 1)');lists.push("COALESCE((SELECT json_agg(t ORDER BY t.name) FROM timeline t),'[]') AS timeline");}
 return {text:'WITH '+ctes.join(',')+' SELECT row_to_json(metrics) AS summary'+(lists.length?','+lists.join(','):'')+' FROM metrics',params:[],columns:cols,measure,category:names.has(cfg.category)?cfg.category:null,secondary:names.has(cfg.secondary)?cfg.secondary:null};
}
async function handler(req,res){
 res.setHeader('Cache-Control','public,max-age=0,s-maxage=180');res.setHeader('X-Content-Type-Options','nosniff');
 if(req.method!=='GET')return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
 const name=typeof req.query?.table==='string'?req.query.table:'dav_product';if(!Object.hasOwn(catalog,name))return res.status(400).json({error:'INVALID_TABLE'});
 if(!process.env.DATABASE_URL)return res.status(503).json({error:'SOURCE_UNAVAILABLE'});
 try{const sql=neon(process.env.DATABASE_URL);const columns=await sql.query('SELECT column_name AS name,data_type AS type FROM information_schema.columns WHERE table_schema=$1 AND table_name=$2 ORDER BY ordinal_position',['public',name]);
  if(!columns.length)return res.status(404).json({error:'TABLE_UNAVAILABLE',table:name});
  const built=buildProfileQuery(name,columns);const [data]=await sql.query(built.text,built.params);const s=data.summary;
  const fields=built.columns.map((c,i)=>({...c,missing:Number(s['m'+i]),unique:Number(s['u'+i])}));
  const stats=built.measure?{field:built.measure,unit:name==='price_record'?'VND theo đơn vị nguồn':'ký tự',n:s.n,mean:s.mean,sd:s.sd,min:s.min,max:s.max,p10:s.p0,q1:s.p1,median:s.p2,q3:s.p3,p90:s.p4}:null;
  return res.status(200).json({mode:'database',table:name,...catalog[name],catalog:Object.entries(catalog).map(([key,c])=>({key,label:c.label,grain:c.grain})),total:Number(s.total),fields,stats,distribution:data.distribution,secondaryDistribution:data.secondary,crossDistribution:data.cross_distribution||[],bins:data.bins||[],timeline:data.timeline||[],categoryField:built.category,secondaryField:built.secondary,refreshedAt:new Date().toISOString(),source:'Neon Gold · public.'+name,countType:'exact',notice:'Mỗi bảng được tổng hợp bằng một truy vấn SQL, không lấy mẫu; thiếu = NULL hoặc chuỗi rỗng sau TRIM. Unique bỏ giá trị thiếu. Không phải báo cáo số dòng đã xóa trong quá khứ.'});
 }catch(e){console.error('Report profile failed',name,e.name);return res.status(503).json({error:'PROFILE_UNAVAILABLE',table:name});}
}
module.exports=handler;module.exports.catalog=catalog;module.exports.buildProfileQuery=buildProfileQuery;
