const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
function load(){
  const element={addEventListener(){},replaceChildren(){}};
  const document={getElementById(){return element;},querySelectorAll(){return[];}};
  return vm.runInNewContext(source+'\n;({stamp})',{document,fetch:()=>new Promise(()=>{}),URLSearchParams});
}
test('timestamps are converted to the timezone printed on the page',()=>{
  const {stamp}=load();
  assert.equal(stamp('2026-11-20T00:00:00Z'),'11-20 08:00 CST');
  assert.equal(stamp('2026-11-20T00:00:00+08:00'),'11-20 00:00 CST');
  assert.equal(stamp('bad timestamp'),'暂无记录');
  assert.equal(stamp(null),'暂无记录');
});
