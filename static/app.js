const $ = s => document.querySelector(s);
const tenant = $('#tenant'), notice = $('#notice');
async function api(path, options={}) {
  const res = await fetch(path, {...options, headers:{'X-Tenant-Id':tenant.value,...options.headers}});
  if (!res.ok) { let err; try { err = await res.json(); } catch { err = {}; } throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail || res.statusText)); }
  return res.status === 204 ? null : res.json();
}
function text(tag, value, cls) { const e = document.createElement(tag); e.textContent = value; if (cls) e.className=cls; return e; }
async function refresh() {
  notice.textContent=''; $('#documents').replaceChildren(); $('#result').hidden=true;
  try { const docs = await api('/api/documents'); if (!docs.length) $('#documents').append(text('p','No documents uploaded yet.','muted'));
    for (const d of docs) { const row=text('div','','doc'), check=document.createElement('input'), label=document.createElement('label'), del=text('button','×','delete'); check.type='checkbox'; check.value=d.id; label.append(text('span',`${d.title} · v${d.version}`),text('small',`${d.valid_from} — ${d.valid_to}`)); del.title='Delete document'; del.onclick=async()=>{if(confirm(`Delete ${d.title} v${d.version}?`)){try{await api(`/api/documents/${d.id}`,{method:'DELETE'});await refresh()}catch(e){notice.textContent=e.message}}}; label.prepend(check); row.append(label,del); $('#documents').append(row); }
  } catch(e) {notice.textContent=e.message;}
}
tenant.onchange=refresh; $('#refresh').onclick=refresh;
$('#upload').onsubmit=async e=>{e.preventDefault();notice.textContent='Indexing document…';const button=e.target.querySelector('button');button.disabled=true;try{await api('/api/documents',{method:'POST',body:new FormData(e.target)});e.target.reset();await refresh();notice.textContent='Document indexed.'}catch(err){notice.textContent=err.message}finally{button.disabled=false}};
function renderChunks(container, chunks) { container.replaceChildren(); if(!chunks.length){container.append(text('p','None.','muted'));return} for(const c of chunks){const card=text('div','','chunk');card.append(text('strong',`${c.title} · v${c.version} · chunk ${c.id} · score ${c.score.toFixed(3)}`),text('p',c.content));container.append(card)} }
$('#ask').onsubmit=async e=>{e.preventDefault();const ids=[...document.querySelectorAll('#documents input:checked')].map(x=>Number(x.value));if(!ids.length){notice.textContent='Select at least one document.';return} notice.textContent='Searching…';const button=e.target.querySelector('button');button.disabled=true;try{const data=await api('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:$('#question').value,document_ids:ids})});$('#answer').textContent=data.answer;renderChunks($('#citations'),data.citations);renderChunks($('#chunks'),data.chunks);$('#result').hidden=false;notice.textContent=''}catch(err){notice.textContent=err.message}finally{button.disabled=false}};
refresh();
