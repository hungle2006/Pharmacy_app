"""Read-only public-data integration check. Never uploads a dataset or patient text."""
from pathlib import Path
import json
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
from ddxplus import refresh
from data_pipeline import validate
from balancing import coverage

def main():
 root=Path(__file__).parent
 path=hf_hub_download(repo_id='leminhhung0101/disease_data',repo_type='dataset',filename='disease_train_ready.parquet')
 rows=pq.read_table(path).to_pylist()
 new,report=refresh(rows,json.loads((root/'ddxplus_sources.json').read_text()),Path('/tmp/ddxplus-pilot'),100,.8)
 assert [r for r in rows if r['split']!='train']==[r for r in new if r['split']!='train']
 validate(new)
 summary={'source':report,'before':coverage(rows,100),'after':coverage(new,100),'frozen_holdouts_unchanged':True}
 print(json.dumps(summary,ensure_ascii=False))
 Path('/tmp/ddxplus-pilot-result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
