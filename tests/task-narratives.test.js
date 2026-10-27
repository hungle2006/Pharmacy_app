'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {validationRows,modelResult}=require('../assets/task-narratives');
test('missing evaluation values stay unavailable instead of turning into perfect zero error',()=>{
 const rows=validationRows({model_comparison:[{name:'temporal_ridge',validation_log_mae:null,validation_gain_pct:null}]});
 assert.equal(rows[0].mae,null);assert.equal(rows[0].gain,null);assert.equal(rows[1].mae,null);
 const r=modelResult({status:'rejected_quality_gate',forecast_change_pct:7,test_gain_fraction:null});
 assert.equal(r.testGain,null);assert.equal(r.estimate,null);assert.equal(r.approved,false);
});
test('actual zero scores remain valid and negative gain is preserved for the diverging chart',()=>{
 const rows=validationRows({validation_baseline_log_mae:0,model_comparison:[{name:'hierarchical',validation_log_mae:0.2,validation_gain_pct:-12.5}]});
 assert.equal(rows[0].mae,0);assert.equal(rows[0].gain,0);assert.equal(rows[1].gain,-12.5);
});
test('rejected models expose only explicitly supplied experimental estimates',()=>{
 const r=modelResult({status:'rejected_quality_gate',reason:'NO_VALIDATION_IMPROVEMENT',forecast_change_pct:9,experimental_change_pct:-0.17});
 assert.equal(r.estimate,-0.17);assert.equal(r.approved,false);assert.match(r.reason,/Chưa chọn mô hình/);
 const approved=modelResult({status:'approved',forecast_change_pct:0,test_gain_fraction:0.02});
 assert.equal(approved.estimate,0);assert.equal(approved.testGain,2);
});
