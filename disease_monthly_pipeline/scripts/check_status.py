"""python scripts/check_status.py MODAL_CALL_ID. Does not start or restart training."""
import sys,json,modal
call=modal.FunctionCall.from_id(sys.argv[1])
try:print(json.dumps(call.get(timeout=0),ensure_ascii=False,indent=2))
except TimeoutError:print('Modal job is still running. No new job was submitted.')
