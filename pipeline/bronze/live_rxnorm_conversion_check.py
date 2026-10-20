"""Opt-in end-to-end source conversion smoke run (no Cloudflare credentials)."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from rxnorm_pipeline import latest,download,convert,gz_csv,COLS
def main():
    url,release=latest()
    with TemporaryDirectory() as root:
        path=Path(root)
        z=path/release
        download(url,z)
        connection=convert(z,path/"rxnorm.sqlite")
        count=connection.execute("SELECT COUNT(*) FROM r").fetchone()[0]
        if count<1000:raise RuntimeError(f"Unexpectedly few terms: {count}")
        out=path/"rxnorm.csv.gz"
        gz_csv(out,COLS,connection.execute("SELECT * FROM r ORDER BY rxcui,tty,display_name"))
        connection.close()
        print(json.dumps({"source":"RxNorm","release":release,"zip_bytes":z.stat().st_size,
                          "rxnorm_rows":count,"csv_gz_bytes":out.stat().st_size,
                          "header":COLS},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
