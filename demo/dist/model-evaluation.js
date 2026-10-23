'use strict';
const $ = id => document.getElementById(id);
const names = {timesfm:'TimesFM · five sessions',market_adjusted:'Market adjustment',event_adjusted:'Country-linked candidate'};
const money = n => Number.isFinite(n) ? n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—';
const text = (tag,value,className) => {const el=document.createElement(tag);el.textContent=value;if(className)el.className=className;return el;};
async function api(path='',options={}) {const r=await fetch('/api/shadow'+path,{credentials:'same-origin',cache:'no-store',...options});const body=await r.json();if(!r.ok){const e=new Error(typeof body.detail==='string'?body.detail:'Request failed.');e.status=r.status;throw e;}return body;}
function signedIn(yes){$('login-panel').hidden=yes;$('evaluation').hidden=!yes;}
function render(data){
  $('issued').textContent=data.counts.issued||0;$('scored').textContent=data.counts.scored||0;
  const latest=data.runs[0];$('run-state').textContent=latest?latest.status:'Not started';$('run-time').textContent=latest?new Date(latest.started_at).toLocaleString():'';
  $('evidence').textContent=data.comparisons.length?'Early prospective results. No model has been approved for public use.':'Insufficient evidence. Comparisons appear once matching five-session forecasts have settled.';
  $('comparisons').replaceChildren();for(const c of data.comparisons){$('comparisons').append(text('div',`${c.candidate} · ${c.matched_forecasts} matched forecasts across ${c.dates} dates. Candidate improvement: ${c.improvement_vs_timesfm_pp.toFixed(3)} pp versus TimesFM; ${c.improvement_vs_market_pp.toFixed(3)} pp versus market adjustment.`,'comparison'));}
  $('metrics').replaceChildren();const max=Math.max(...data.metrics.map(m=>m.mae_pp),.001);
  if(!data.metrics.length)$('metrics').append(text('p','No scored outcomes yet.','muted'));
  for(const m of data.metrics){const row=text('div','','metric');row.append(text('span',`${names[m.model]||m.model} (${m.scored})`));const track=text('div','','track'),bar=text('div','','bar');bar.style.width=`${100*m.mae_pp/max}%`;track.append(bar);row.append(track,text('span',m.mae_pp.toFixed(3)));row.title=m.candidate;$('metrics').append(row);}
  $('predictions').replaceChildren();for(const p of data.predictions){const row=document.createElement('tr');const state=p.scoring_issue?'Needs review':p.actual!==null?'Scored':'Pending';for(const value of [p.symbol,p.cutoff,p.target,names[p.model]||p.model,money(p.payload.predicted),money(p.actual),p.evaluation?p.evaluation.absolute_error_pp.toFixed(3):'—',state])row.append(text('td',value));row.title=p.scoring_issue||`${p.candidate} · issued ${p.issued_at}`;$('predictions').append(row);}
  if(!data.predictions.length){const row=document.createElement('tr');const cell=text('td','No prospective shadow forecasts have been issued yet.');cell.colSpan=8;row.append(cell);$('predictions').append(row);}
  $('runs').replaceChildren();if(!data.runs.length)$('runs').append(text('p','Waiting for the first scheduled shadow run.','muted'));
  for(const r of data.runs){const row=text('div','','run');row.append(text('strong',r.status),text('span',new Date(r.started_at).toLocaleString()),text('p',r.detail.candidate_skip_reason||r.detail.reason||`Cutoff ${r.cutoff||'—'} · newly scored: ${r.detail.newly_scored||0}`));$('runs').append(row);}
}
async function refresh(){ $('status').textContent='Loading private evaluation…';try{const data=await api();signedIn(true);render(data);$('status').textContent='Updated '+new Date().toLocaleTimeString();$('status').className='';}catch(e){if(e.status===401||e.status===503)signedIn(false);$('status').textContent=e.message;$('status').className='error';}}
$('login-form').addEventListener('submit',async e=>{e.preventDefault();const token=$('token').value;$('token').value='';try{await api('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});await refresh();}catch(error){$('status').textContent=error.message;$('status').className='error';}});
$('refresh').addEventListener('click',refresh);
$('logout').addEventListener('click',async()=>{await api('/logout',{method:'POST'});signedIn(false);$('status').textContent='Signed out.';$('predictions').replaceChildren();$('metrics').replaceChildren();$('runs').replaceChildren();$('comparisons').replaceChildren();});
(async()=>{try{const session=await api('/session');if(session.authenticated)await refresh();else{$('status').textContent='Sign in to view saved shadow forecasts.';signedIn(false);}}catch(e){$('status').textContent=e.message;}})();
