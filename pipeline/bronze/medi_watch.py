import os,re,json,sys
from datetime import datetime,timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
URL="https://www.vumc.org/wei-lab/medi"
def inspect(html):
    soup=BeautifulSoup(html,"html.parser")
    text=soup.get_text(" ",strip=True)
    versions=sorted({int(x) for x in re.findall(r"\bMEDI[-_\s]+(\d+)(?=\D|$)",text,re.I) if int(x)>2})
    links=[{"text":a.get_text(" ",strip=True),"url":urljoin(URL,a["href"])} for a in soup.select("a[href]") if re.search(r"MEDI[-_ ]*[3-9]\d*.*HPS",a.get_text(" ",strip=True),re.I)]
    return {"source":URL,"versions_after_medi2":versions,"candidate_hps_links":links}
def main():
    r=requests.get(URL,timeout=45,headers={"User-Agent":"PharmaBiz research monitor/1.0"})
    r.raise_for_status()
    result=inspect(r.text)
    result["checked_utc"]=datetime.now(timezone.utc).isoformat()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a") as f:f.write("\n### MEDI HPS version check\n"+json.dumps(result,ensure_ascii=False)+"\n")
    if result["versions_after_medi2"] or result["candidate_hps_links"]:
        print("::warning::New MEDI release candidate, review before download")
        return 2
    return 0
if __name__=="__main__":sys.exit(main())
