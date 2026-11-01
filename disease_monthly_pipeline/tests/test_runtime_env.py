"""Verify actual pinned Hub backend selection in a fresh interpreter."""
import os,subprocess,sys,json
from pathlib import Path

def test_hub_disables_xet_before_import_and_keeps_checkpoint_cache_persistent():
 root=Path(__file__).resolve().parents[1]
 code="""
from runtime_env import configure_environment
configure_environment()
import os,json,sys
from huggingface_hub import constants
from huggingface_hub.utils._runtime import is_xet_available
print(json.dumps({'disabled':constants.HF_HUB_DISABLE_XET,'xet_available':is_xet_available(),'xet_imported':'hf_xet' in sys.modules,'hf_home':constants.HF_HOME,'xet_cache':os.environ['HF_XET_CACHE'],'model_cache':os.environ['MODEL_CACHE']}))
"""
 env={**os.environ,'PYTHONPATH':str(root)+os.pathsep+os.environ.get('PYTHONPATH',''),'HF_HUB_DISABLE_XET':'0','HF_XET_CACHE':'/storage/unsafe-xet'}
 response=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,check=True,timeout=30)
 result=json.loads(response.stdout.strip())
 assert result['disabled'] is True and result['xet_available'] is False
 assert result['xet_imported'] is False
 assert result['xet_cache'].startswith('/tmp/')
 assert result['hf_home']=='/storage/hf_home' and result['model_cache']=='/storage/hf_cache'
