import argparse,json,os
import modal
p=argparse.ArgumentParser();p.add_argument('--force',action='store_true');p.add_argument('--approve-new-benchmark',action='store_true');a=p.parse_args()
for name in ['MODAL_TOKEN_ID','MODAL_TOKEN_SECRET']:
 if not os.getenv(name):raise SystemExit('Missing '+name+' in GitHub Actions Secrets')
f=modal.Function.from_name('disease-monthly-pipeline','pipeline')
call=f.spawn(force=a.force,submission_id=os.getenv('GITHUB_RUN_ID','manual')+'-'+os.getenv('GITHUB_RUN_ATTEMPT','1'),allow_new_benchmark=a.approve_new_benchmark)
result={'submitted':True,'modal_call_id':call.object_id,'note':'GitHub success means submission accepted; inspect Modal for training completion.'}
open('submission.json','w').write(json.dumps(result,indent=2));print(json.dumps(result))
if os.getenv('GITHUB_STEP_SUMMARY'):
 with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as s:s.write('## Disease training submitted\n\nModal call: `'+call.object_id+'`\n\nTraining continues on Modal after this job exits. No claim that training or deployment has completed.\n')
