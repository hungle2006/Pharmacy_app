"""Small, read-only network checks of upstream public sources (no R2 writes)."""
import json
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from crawl_dav import DEFAULT_BASE_URL, prepare_session, get_page
from crawl_icd10 import root_url
from medi_watch import URL as MEDI_URL, inspect
from rxnorm_pipeline import latest

def test_source(name, check):
    try:
        result = check()
        print(json.dumps({"source":name,"ok":True,"result":result},ensure_ascii=False))
        return True
    except Exception as exc:
        print(json.dumps({"source":name,"ok":False,"error":str(exc)[:350]},ensure_ascii=False))
        return False

def dav():
    session,_ = prepare_session(DEFAULT_BASE_URL)
    try:
        page = get_page(session, DEFAULT_BASE_URL, skip=0, size=1, retries=1)
        return {"items_received":len(page["items"]),"totalCount":page.get("totalCount")}
    finally:session.close()

def icd():
    r=requests.get(root_url("vi"),timeout=30);r.raise_for_status()
    data=r.json()
    if data.get("status")!="success" or not isinstance(data.get("data"),list):raise RuntimeError("Unexpected ICD-10 response")
    return {"root_nodes":len(data["data"])}

def rxnorm():
    url,release=latest()
    return {"release":release,"download_url":url}

def medi():
    r=requests.get(MEDI_URL,timeout=30);r.raise_for_status()
    status=inspect(r.text)
    return {"versions_after_medi2":status["versions_after_medi2"],"candidate_links":len(status["candidate_hps_links"])}

def main():
    checks=[("DAV",dav),("ICD-10",icd),("RxNorm",rxnorm),("MEDI",medi)]
    results=[(name,test_source(name,fn)) for name,fn in checks]
    with open("/tmp/pharmacy-source-health.json","w") as f:
        json.dump({"time":datetime.now(timezone.utc).isoformat(),"results":dict(results)},f)
    return 0 if all(ok for _,ok in results) else 1

if __name__=="__main__":sys.exit(main())
