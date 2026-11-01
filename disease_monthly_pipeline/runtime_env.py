"""Configure Hub before imports; persistent checkpoints must not host open Xet logs."""
import os

def configure_environment():
 os.environ.update({
  'HF_HOME':'/storage/hf_home',
  'MODEL_CACHE':'/storage/hf_cache',
  'HF_HUB_DISABLE_XET':'1',
  'HF_XET_CACHE':'/tmp/disease-hf-xet',
 })
