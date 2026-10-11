'use strict';
const $ = (id) => document.getElementById(id);
const labels = { valid:'数据有效', stale:'数据过期', missing:'数据缺测', invalid:'时间异常' };
const state = { assets:[], selected:'D-01', group:'', query:'', snapshot:'', detailVersion:0, recordVersion:0 };
const svgNS = 'http://www.w3.org/2000/svg';
function text(id,value) { $(id).textContent = value; }
function svg(tag,attrs={},value) { const el=document.createElementNS(svgNS,tag); Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v)); if(value!==undefined) el.textContent=value; return el; }
function stamp(value) { return value ? value.slice(5,16).replace('T',' ')+' CST' : '暂无记录'; }
async function api(url) { const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`数据读取失败（${r.status}），请检查本地服务。`); return r.json(); }
function error(err) { text('error',err.message); $('error').hidden=false; }
function clearError() { $('error').hidden=true; }

function renderLayout() {
  const assets=state.assets.filter(a=>(!state.group||a.group_name===state.group)&&(!state.query||(a.id+' '+a.name).toLowerCase().includes(state.query.toLowerCase())));
  text('visible-count',`${assets.length} / ${state.assets.length} 个构件`);
  const canvas=svg('svg',{viewBox:'0 0 780 390',role:'group','aria-label':'吊盘与保护棚二维布置示意'});
  canvas.append(svg('rect',{x:30,y:37,width:720,height:138,rx:16,class:'zone'}),svg('rect',{x:30,y:207,width:720,height:138,rx:16,class:'zone'}));
  canvas.append(svg('text',{x:47,y:28,class:'zone-name'},'保护棚 / 上层示意'),svg('text',{x:47,y:198,class:'zone-name'},'吊盘 / 下层示意'));
  for(const a of assets) {
    const group=svg('g',{transform:`translate(${a.x-45} ${a.y-20})`,class:`asset ${a.id===state.selected?'active':''}`,role:'button',tabindex:'0','aria-label':`选择 ${a.id} ${a.name} ${labels[a.quality]}`,'aria-pressed':a.id===state.selected});
    group.append(svg('rect',{width:190,height:90,rx:8}),svg('circle',{cx:169,cy:19,r:4,class:a.quality+'-dot'}),svg('text',{x:16,y:30,class:'id-text'},a.id),svg('text',{x:16,y:54},a.name),svg('text',{x:16,y:75,class:'quality-text'},labels[a.quality]));
    group.addEventListener('click',()=>selectAsset(a.id));
    group.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectAsset(a.id);}});
    canvas.append(group);
  }
  if(!assets.length) canvas.append(svg('text',{x:390,y:183,'text-anchor':'middle',class:'zone-name'},'没有匹配的构件，请调整搜索条件'));
  $('layout').replaceChildren(canvas);
}

function renderChart(data) {
  const chart=svg('svg',{viewBox:'0 0 410 130',role:'img','aria-label':`${data.asset_id} 示例温度历史序列，缺测不连线`});
  const present=data.items.map(p=>p.value).filter(v=>v!==null&&Number.isFinite(v));
  if(!present.length) {chart.append(svg('text',{x:205,y:66,'text-anchor':'middle',class:'empty'},'暂无有效样例数据'));$('chart').replaceChildren(chart);return;}
  const low=Math.floor((Math.min(...present)-.2)*10)/10,high=Math.ceil((Math.max(...present)+.2)*10)/10;
  const y=v=>99-(v-low)/(high-low)*78;
  for(let j=0;j<3;j++){const value=low+(high-low)*j/2, yy=y(value);chart.append(svg('line',{x1:40,y1:yy,x2:398,y2:yy,class:'grid-line'}),svg('text',{x:32,y:yy+3,'text-anchor':'end'},value.toFixed(1)));}
  let d='',connected=false;
  data.items.forEach((p,i)=>{if(p.value===null||!Number.isFinite(p.value)){connected=false;return;}const x=40+i*358/Math.max(1,data.items.length-1);d+=`${connected?'L':'M'}${x.toFixed(1)},${y(p.value).toFixed(1)} `;connected=true;});
  chart.append(svg('path',{d,class:'line'}));
  if(data.items.length)chart.append(svg('text',{x:40,y:120},data.items[0].timestamp.slice(11,16)),svg('text',{x:398,y:120,'text-anchor':'end'},data.items.at(-1).timestamp.slice(11,16)));
  $('chart').replaceChildren(chart);
}

function recordQuery() { const q=new URLSearchParams(); if($('scope').value==='selected')q.set('asset_id',state.selected);if($('stage').value)q.set('stage',$('stage').value);return q; }
function showRecord(row) {
  const pairs=[['记录编号',row.id],['构件编号',row.asset_id],['记录时间',stamp(row.timestamp)],['作业阶段',row.stage],['记录事项',row.title],['来源结果',row.result],['记录说明',row.note]];
  $('record-detail').replaceChildren(...pairs.map(([key,val])=>{const div=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=key;dd.textContent=val;div.append(dt,dd);return div;}));
  $('record-dialog').showModal();
}
async function loadRecords() {
  const version=++state.recordVersion,q=recordQuery();
  $('export').href='/api/records.csv?'+q;
  try {
    const data=await api('/api/records?'+q);
    if(version!==state.recordVersion)return;
    text('record-count',`${data.total} 条`);
    const rows=data.items.map(row=>{const tr=document.createElement('tr');for(const key of ['timestamp','asset_id','stage','title','result']){const td=document.createElement('td');td.textContent=key==='timestamp'?stamp(row[key]):row[key];if(key==='result'){const badge=document.createElement('span');badge.className='tag'+(row.result==='待复核'?' pending':'');badge.textContent=row.result;td.replaceChildren(badge);}tr.append(td);}const td=document.createElement('td'),btn=document.createElement('button');btn.className='row-detail';btn.textContent='查看';btn.setAttribute('aria-label',`查看记录 ${row.id}`);btn.addEventListener('click',()=>showRecord(row));td.append(btn);tr.append(td);return tr;});
    if(!rows.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=6;td.className='empty-row';td.textContent='该筛选条件下暂无记录';tr.append(td);rows.push(tr);}
    $('rows').replaceChildren(...rows);
  }catch(err){if(version===state.recordVersion)error(err);}
}
async function selectAsset(id) {
  const version=++state.detailVersion;
  state.selected=id;renderLayout();clearError();
  text('asset-name','正在读取');text('asset-id',id);text('value','—');text('observed','—');text('region','—');text('source-state','');text('quality-badge','读取中');$('chart').replaceChildren();
  loadRecords();
  try {
    const [detail,series]=await Promise.all([api('/api/assets/'+id),api('/api/assets/'+id+'/series')]);
    if(version!==state.detailVersion)return;
    const a=detail.asset;
    text('asset-name',a.name);text('asset-id',a.id);text('region',a.region);text('source-state','来源状态 / '+a.source_status);text('observed',stamp(a.observed_at));text('quality-badge',labels[a.quality]);$('quality-badge').className='quality-badge '+a.quality;
    text('value',a.value===null?'—':a.value.toFixed(1));
    text('value-note',a.quality==='stale'?'该值为过期样例，不表示当前状态':a.quality==='missing'?'未提供测值；不替换为零，不生成安全结论':'演示指标，不用于工程判断');
    renderChart(series);
  }catch(err){if(version===state.detailVersion)error(err);}
}

document.querySelectorAll('[data-group]').forEach(btn=>btn.addEventListener('click',()=>{state.group=btn.dataset.group;document.querySelectorAll('[data-group]').forEach(b=>b.classList.toggle('selected',b===btn));renderLayout();}));
$('search').addEventListener('input',e=>{state.query=e.target.value;renderLayout();});
['scope','stage'].forEach(id=>$(id).addEventListener('change',loadRecords));
$('close-dialog').addEventListener('click',()=>$('record-dialog').close());
async function start() {
  try {const [summary,assets]=await Promise.all([api('/api/summary'),api('/api/assets')]);state.assets=assets.items;state.snapshot=summary.snapshot;text('total',summary.total);text('valid',summary.quality_counts.valid);text('stale',summary.quality_counts.stale);text('missing',summary.quality_counts.missing);text('snapshot',stamp(summary.snapshot));await selectAsset(state.selected);}catch(err){error(err);}
}
start();

