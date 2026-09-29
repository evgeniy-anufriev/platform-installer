const {test}=require('node:test');
const assert=require('node:assert/strict');
const {withNativeDialog}=require('./qa-native-dialog.cjs');
function page(supported=true) {
  const calls=[];
  return {calls, evaluate: async fn => {
    const source=String(fn);
    if(source.includes('typeof')) return supported;
    calls.push(source.includes('WindowHide')?'hide':'show');
  }, waitForTimeout: async () => calls.push('wait')};
}
test('restores owner after successful native action',async()=>{
  const p=page();
  assert.equal(await withNativeDialog(p,async()=>{p.calls.push('action');return 'CANCELLED'}),'CANCELLED');
  assert.deepEqual(p.calls,['hide','wait','action','show']);
});
test('restores owner on selection failure',async()=>{
  const p=page();
  await assert.rejects(withNativeDialog(p,async()=>{p.calls.push('action');throw Error('SELECTION_FAILED')}),/SELECTION_FAILED/);
  assert.deepEqual(p.calls,['hide','wait','action','show']);
});
test('missing runtime fails before native action',async()=>{
  const p=page(false);
  await assert.rejects(withNativeDialog(p,async()=>assert.fail('action must not run')),/RUNTIME_UNAVAILABLE/);
  assert.deepEqual(p.calls,[]);
});
