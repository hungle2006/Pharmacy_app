"""Render API: small proxy by default; optional local backend for a memory-sized paid service."""
import asyncio,hmac,os
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException,Header,Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field

def backend():return os.getenv('INFERENCE_BACKEND','modal')
@asynccontextmanager
async def lifespan(app):
 if not os.getenv('API_KEY'):raise RuntimeError('Set API_KEY in Render Environment before starting')
 if backend() not in ['modal','local']:raise RuntimeError('INFERENCE_BACKEND must be modal or local')
 if backend()=='modal' and not all(os.getenv(k) for k in ['MODAL_TOKEN_ID','MODAL_TOKEN_SECRET']):raise RuntimeError('Configure Modal service credentials in Render Environment')
 yield
app=FastAPI(title='Disease Research API',lifespan=lifespan)
origins=[x.strip() for x in os.getenv('CORS_ORIGINS','').split(',') if x.strip()]
if origins:app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST'],allow_headers=['Content-Type','X-API-Key'])
async def authorized(x_api_key:str=Header(default='')):
 expected=os.getenv('API_KEY','')
 if not expected or not hmac.compare_digest(x_api_key,expected):raise HTTPException(401,'Invalid API key')
class Input(BaseModel):
 text:str=Field(min_length=5,max_length=4000)
 top_k:int=Field(default=5,ge=1,le=10)
@app.get('/health')
async def health():return {'status':'ok','backend':backend(),'scope':'process health; model is loaded on first authenticated prediction'}
@app.post('/predict',dependencies=[Depends(authorized)])
async def predict(body:Input):
 try:
  if backend()=='modal':
   import modal
   fn=modal.Function.from_name(os.getenv('MODAL_APP_NAME','disease-monthly-pipeline'),'predict')
   return await asyncio.wait_for(fn.remote.aio(body.text,body.top_k),timeout=240)
  from inference import predict_text
  return await asyncio.to_thread(predict_text,body.text,body.top_k)
 except asyncio.TimeoutError:raise HTTPException(504,'Model startup/prediction timed out; retry later')
 except Exception:raise HTTPException(503,'Model unavailable. Check deployment and private logs; no patient text is logged by this API.')
