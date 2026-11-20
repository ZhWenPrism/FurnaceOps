const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
test('startup selects the first available asset instead of a missing default',async()=>{
  const elements=new Map(),pending=[];
  function el(){return {children:[],addEventListener(){},setAttribute(){},append(...c){this.children.push(...c);},
    replaceChildren(...c){this.children=c;}};}
  const document={querySelectorAll:()=>[],getElementById(id){if(!elements.has(id))elements.set(id,el());return elements.get(id);},
    createElementNS:()=>el(),createElement:()=>el()};
  const data={'/api/summary':{total:1,snapshot:'2026-11-20T00:00:00Z',quality_counts:{}},
    '/api/assets':{items:[{id:'P-99',name:'synthetic',x:0,y:0,quality:'valid'}]}};
  const fetch=url=>{if(url in data)return Promise.resolve({ok:true,json:async()=>data[url]});pending.push(url);return new Promise(()=>{});};
  const view=vm.runInNewContext(source+'\n;({state})',{document,fetch,URLSearchParams});
  await new Promise(r=>setImmediate(r));
  assert.equal(view.state.selected,'P-99');
  assert.ok(pending.includes('/api/assets/P-99'));
  assert.ok(!pending.includes('/api/assets/D-01'));
});
