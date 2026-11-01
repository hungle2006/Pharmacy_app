"""Fixed CPU reference. Fits vocabulary and NB on train only; no parameter search."""
import argparse,hashlib,json
import numpy as np
import pyarrow.parquet as pq
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score,f1_score

def run(path):
 rows=pq.read_table(path).to_pylist();train=[r for r in rows if r['split']=='train']
 vectorizer=TfidfVectorizer(ngram_range=(1,2),max_features=30000,min_df=2,sublinear_tf=True,dtype=np.float32)
 model=MultinomialNB(alpha=.5).fit(vectorizer.fit_transform([r['text'] for r in train]),[r['label_id'] for r in train])
 result={'dataset_sha256':hashlib.sha256(open(path,'rb').read()).hexdigest(),'train_rows':len(train),'method':'TF-IDF word unigrams/bigrams, max_features=30000, min_df=2, sublinear_tf=True, MultinomialNB alpha=0.5; no parameter search','scope':'same-source research baseline, not clinical diagnostic accuracy'}
 for split in ['validation','test']:
  subset=[r for r in rows if r['split']==split];truth=[r['label_id'] for r in subset];prediction=model.predict(vectorizer.transform([r['text'] for r in subset]))
  result[split]={'n':len(subset),'accuracy':float(accuracy_score(truth,prediction)),'macro_f1':float(f1_score(truth,prediction,average='macro',zero_division=0))}
 return result
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('data');args=parser.parse_args();print(json.dumps(run(args.data),ensure_ascii=False,indent=2))
