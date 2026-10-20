"""Read-only columns and basic sizes of existing R2 seed files."""
import os,io,json,gzip,openpyxl,boto3,csv
s=boto3.client("s3",region_name="auto",endpoint_url="https://"+os.environ["R2_ACCOUNT_ID"]+".r2.cloudflarestorage.com",aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
bucket="pharmacy-data-lake"
for key in ["DAV.xlsx","ICD10_Vietnam.xlsx","rxnorm.xlsx","MEDI-2_HPS.xlsx"]:
    obj=s.get_object(Bucket=bucket,Key=key)
    wb=openpyxl.load_workbook(io.BytesIO(obj["Body"].read()),read_only=True,data_only=True)
    ws=wb.active;it=ws.values;row=next(it)
    print(json.dumps({"file":key,"sheet":ws.title,"headers":[str(x) for x in row],"sample":[str(x)[:60] if x is not None else "" for x in next(it)],"rows_estimate":ws.max_row},ensure_ascii=False),flush=True)
for kind in ["icd10","rxnorm"]:
    obj=json.loads(s.get_object(Bucket=bucket,Key=f"_control/{kind}/latest.json")["Body"].read())
    data=s.get_object(Bucket=bucket,Key=obj["snapshot"])["Body"].read()
    with gzip.open(io.BytesIO(data),"rt",encoding="utf-8") as f:
        print(json.dumps({"previous_snapshot":kind,"headers":next(csv.reader(f))},ensure_ascii=False))
