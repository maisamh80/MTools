import {localize} from './i18n.js';
import {ProjectPanel} from './projects.js';
const stylesheet = new URL('./style.css', import.meta.url).href;
const logo = new URL('./MTool.svg', import.meta.url).href;
export const bytes = (n = 0) => n < 1024 ? `${n} B` : n < 1048576 ? `${(n/1024).toFixed(1)} KiB` : n < 1073741824 ? `${(n/1048576).toFixed(1)} MiB` : `${(n/1073741824).toFixed(1)} GiB`;
const escape = (s = '') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const badge = (status) => `<span class="badge ${status === 'found' || status === 'complete' || status === 'loaded' ? 'good' : 'warn'}">${escape(status.replaceAll('_',' '))}</span>`;
const placeholderNames = ['lavender', 'amber', 'mint', 'arctic'];
const placeholderImages = placeholderNames.map(name => new URL(`./placeholders/${name}.png`, import.meta.url).href);
const art = (item, large=false) => {
  const index = (Number.parseInt(item.id?.slice(-2)||'0',16)||0)%4;
  return `<img class="cover ${large?'large':''}" src="${escape(item.cover || placeholderImages[index])}" alt="${escape(item.title)} cover">`;
};
const download = (name, text, type='application/json') => {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const a = document.createElement('a'); a.href=url; a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
};

export async function mount(host, api, integration = {}) {
  const root = host.attachShadow({mode:'open'});
  root.innerHTML = `<link rel="stylesheet" href="${stylesheet}"><div class="workspace-backdrop" aria-hidden="true"></div><section class="shell" aria-label="M Tools">
    <header><div class="brand"><img src="${logo}" alt=""><strong>M Tools</strong><span class="edition">PORTABLE</span></div>
    <div class="header-right"><span class="live-dot"></span><span>${api.demo?'Design preview · sample data':'Your local creative workspace'}</span><button data-action="close" class="icon-button" aria-label="Close M Tools">×</button></div></header>
    <nav aria-label="Sections"><div class="tabs">${[['workflows','◇','Workflows'],['projects','▱','Projects'],['reports','◫','Reports'],['gallery','▧','Gallery']].map(([id,icon,label])=>`<button aria-label="${label}" data-tab="${id}"><span>${icon}</span>${label}</button>`).join('')}</div><button data-tab="settings" aria-label="Settings" class="settings-tab">⚙ <span>Settings</span></button></nav>
    <div class="notice" role="status" hidden></div><main></main><div class="job" hidden></div>
    <footer><span><span class="live-dot"></span> PRIVATE WORKSPACE</span><span>Nothing runs until you choose · M Tools 1.0.0</span></footer></section><div class="modal-layer"></div>`;
  const $ = s => root.querySelector(s);
  const state = {tab:integration.initialTab||'workflows', items:[], selected:null, detail:null, query:'', report:null, gallery:[], selectedFiles:new Set(), alive:true, job:null, deleted:false};
  const signal = new AbortController();
  const main = $('main');
  let noticeTimer;
  function notice(text, error=false) {
    clearTimeout(noticeTimer);
    const el=$('.notice'); if(!el||!state.alive)return;
    el.hidden=!text; el.innerHTML=text?`<span>${escape(text)}</span><button data-action="dismiss-notice" aria-label="Dismiss notification">×</button>`:'';
    el.classList.toggle('error',error);
    if(text&&!error)noticeTimer=setTimeout(()=>notice(''),6000);
  }
  async function safe(fn) { try {return await fn();} catch(e) {notice(e.message,true);} }
  const call = (method, params) => api.call(method, params);
  function heading(kicker,title,description,actions='') {return `<div class="page-heading"><div><div class="eyebrow">${kicker}</div><h1>${title}</h1><p>${description}</p></div><div class="actions">${actions}</div></div>`;}
  const projects=new ProjectPanel(main,api,integration,{modal,notice,startJob,coverData,download,bytes});
  function render() {
    if(!state.alive)return;
    root.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===state.tab);b.setAttribute('aria-current',b.dataset.tab===state.tab?'page':'false');});
    if(state.tab==='workflows') renderWorkflows();
    if(state.tab==='reports') renderReports();
    if(state.tab==='gallery') renderGallery();
    if(state.tab==='settings') renderSettings();
    if(state.tab==='projects') projects.render();
  }
  async function refresh() {
    notice('');
    if(state.tab==='workflows') {
      state.items=await call('workflows',{deleted:state.deleted});
      if(state.selected) state.detail=await call('workflow.get',{id:state.selected});
    }
    if(state.tab==='reports') state.report=await call('report');
    if(state.tab==='settings')projects.root=(await call('projects')).root;
    if(state.tab==='projects') await projects.refresh();
    if(state.tab==='gallery') { const data=await call('gallery'); state.gallery=data.files; state.selectedFiles.clear(); if(data.errors.length) notice(`${data.errors.length} paths could not be read.`,true); }
    render();
  }
  function renderWorkflows() {
    const filtered=state.items.filter(w=>`${w.title} ${w.description} ${w.tags.join(' ')}`.toLowerCase().includes(state.query.toLowerCase()));
    main.innerHTML=heading('CREATE. COLLECT. RETURN.',state.deleted?'Workflow recovery':'Your workflows','A home for the workflows worth keeping.',`<button data-action="toggle-deleted">${state.deleted?'Back to library':'Recovery'}</button><button class="primary" data-action="add">＋ Add workflow</button>`)+
      `<div class="toolbar"><label class="search">⌕ <input aria-label="Search workflows" placeholder="Search workflows, descriptions or tags" value="${escape(state.query)}" data-search="workflows"></label><span class="muted">${filtered.length} workflows</span></div>
      <div class="library-layout"><div class="cards">${filtered.map(w=>`<article class="workflow-card ${state.selected===w.id?'selected':''}"><button class="card-main" data-select="${w.id}">${art(w)}<div class="card-copy"><div class="card-title">${escape(w.title)}</div><p>${escape(w.description || 'No description yet')}</p><div class="tags">${w.tags.slice(0,3).map(t=>`<span>${escape(t)}</span>`).join('')}</div></div></button><div class="card-footer"><span>REV ${w.revision}</span><div><button data-edit="${w.id}">Edit</button><button data-open-workflow="${w.id}">Open in New Tab</button><button data-export="${w.id}">Export ↗</button></div></div></article>`).join('')||`<div class="empty"><span>◇</span><h2>Your collection starts here</h2><p>Save the active tab or import a workflow JSON.</p><button class="primary" data-action="add">Add your first workflow</button></div>`}</div><aside class="detail">${detailHTML()}</aside></div>`;
  }
  function detailHTML() {
    const w=state.detail;
    if(!w) return `<div class="empty detail-empty"><span>⌘</span><h2>A closer look</h2><p>Select a workflow to see its details and check what it needs.</p><div class="mini-nodes"><i></i><i></i><i></i></div><small>Selecting a card never runs a workflow.</small></div>`;
    return `<div class="detail-top"><span class="eyebrow">WORKFLOW DETAILS</span><button data-action="deselect" aria-label="Close details">×</button></div>${art(w,true)}<h2>${escape(w.title)}</h2><p class="description">${escape(w.description||'No description')}</p><div class="tags">${w.tags.map(t=>`<span>${escape(t)}</span>`).join('')}</div>
      <div class="requirements"><div class="section-label">Requirements <button data-action="check">↻ Recheck</button></div><div class="check-result">${w.check?checkHTML(w.check):'<p class="muted">Checking local requirements…</p>'}</div></div>
      <div class="detail-actions"><button class="primary" data-action="open">Open in new tab ↗</button><div class="two"><button data-edit="${w.id}">Edit details</button><button data-export="${w.id}">Export</button></div><div class="two"><button data-action="revision">Restore revision</button><button class="danger-text" data-action="delete-workflow">${w.deleted?'Restore workflow':'Remove from library'}</button></div></div>`;
  }
  function checkHTML(r) { return `${badge(r.status)}<p class="small muted">${new Date(r.checked_at*1000).toLocaleString()}</p>${r.models.map(m=>`<div class="requirement"><div><strong>${escape(m.name||m.type)}</strong><small>${escape(m.target||m.category)}${m.reason?` · ${escape(m.reason)}`:''}</small></div>${badge(m.status)}</div>`).join('')}${r.custom_nodes.map(n=>`<div class="requirement"><div><strong>${escape(n.type)}</strong><small>Custom node${n.repository?` · <a href="${escape(n.repository)}" target="_blank" rel="noopener noreferrer">Repository ↗</a>`:''}</small></div>${badge(n.status)}</div>`).join('')}${r.unresolved.map(n=>`<div class="requirement"><div><strong>${escape(n.type)}</strong><small>${escape(n.reason)}</small></div>${badge('unsupported')}</div>`).join('')}<p class="small muted">${escape(r.notice)}</p>`; }
  async function select(id) {
    state.selected=id; state.detail=await call('workflow.get',{id}); render();
    const report=await call('workflow.check',{id});
    if(state.selected===id && state.detail) {state.detail.check=report;render();}
  }
  function fileName(path) {return String(path).split(/[\\/]/).pop();}
  function reportFolder(g) {
    if(!g.count)return `<div class="folder empty-folder" aria-disabled="true"><div class="empty-summary"><span class="folder-symbol">▱</span><strong>${escape(g.name)}</strong><span>Empty</span><b>0 B</b></div></div>`;
    return `<details class="folder"><summary><span class="folder-symbol">▱</span><strong>${escape(g.name)}</strong><span>${g.count} files</span><b>${bytes(g.size)}</b><span>⌄</span></summary><div class="file-table">${g.files.filter(f=>!state.query||g.name.toLowerCase().includes(state.query.toLowerCase())||f.path.toLowerCase().includes(state.query.toLowerCase())).map(f=>`<div class="file-row"><div><strong>${escape(fileName(f.path))}</strong><small>${escape(f.absolute_path||'')}</small></div><span>${bytes(f.size)}</span><button data-copy="${escape(f.absolute_path||f.path)}">Copy path</button>${f.source_url?`<a href="${escape(f.source_url)}" rel="noopener noreferrer" target="_blank">Source ↗</a>`:'<span class="muted">Source unknown</span>'}</div>`).join('')}</div></details>`;
  }
  function renderReports() {
    const r=state.report;
    main.innerHTML=heading('KNOW YOUR WORKSPACE','Storage, without the guesswork','Every model folder. Every file. Empty folders included.',`<button data-action="report-csv">Export CSV</button><button data-action="report-json">Export JSON</button><button class="primary" data-action="scan">↻ Scan storage</button>`)+
      (!r?'<div class="empty"><span>◫</span><h2>Let’s map your installation</h2><p>A read-only scan reports model folders and logical file sizes.</p><button class="primary" data-action="scan">Start first scan</button></div>':
      `<div class="stats"><div class="stat"><span>PORTABLE INSTALLATION</span><strong>${bytes(r.portable_bytes)}</strong><small>Entire portable folder</small></div><div class="stat"><span>COMFYUI FOLDER</span><strong>${bytes(r.comfy_bytes)}</strong><small>Included in portable total</small></div><div class="stat accent"><span>MODEL FILES</span><strong>${bytes(r.models_bytes)}</strong><small>${r.groups.reduce((s,g)=>s+g.count,0)} files across ${r.groups.length} categories</small></div><div class="stat"><span>LAST SCAN</span><strong class="smaller">${new Date(r.scanned_at*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</strong><small>${r.errors.length?'Incomplete · '+r.errors.length+' errors':'Snapshot available'}</small></div></div>
      <div class="report-caption"><span>${escape(r.measurement)}</span><span>Unique file bytes: ${bytes(r.portable_unique_bytes)}</span></div>
      <div class="toolbar"><label class="search">⌕ <input data-search="reports" aria-label="Search model files" value="${escape(state.query)}" placeholder="Search folders and model files"></label><span class="muted">All physical folder names preserved</span></div>
      <div class="folder-list">${r.groups.filter(g=>g.name.toLowerCase().includes(state.query.toLowerCase())||g.files.some(f=>f.path.toLowerCase().includes(state.query.toLowerCase()))).map(reportFolder).join('')}</div>${r.external?.length?`<h2>Additional model folders</h2><p class="muted">Model locations registered by ComfyUI outside its main models folder.</p>${r.external.map(e=>`<details class="folder"><summary>${escape(e.category)} · ${escape(e.root)}</summary><div class="file-table">${(e.files||[]).map(f=>`<div class="file-row"><div><strong>${escape(fileName(f.path))}</strong><small>${escape(e.root)}/${escape(f.path)}</small></div><span>${bytes(f.size)}</span></div>`).join('')}<p>${escape(JSON.stringify(e.errors))}</p></div></details>`).join('')}`:''}${r.errors.length?`<details class="folder"><summary>Scan errors (${r.errors.length})</summary><pre>${escape(JSON.stringify(r.errors,null,2))}</pre></details>`:''}`);
  }
  function renderGallery() {
    const filter=state.galleryFilter||'all';
    const items=state.gallery.filter(f=>(filter==='all'||f.kind===filter)&&f.path.toLowerCase().includes(state.query.toLowerCase())).sort((a,b)=>state.sort==='size'?b.size-a.size:b.mtime_ns-a.mtime_ns);
    state.filteredGallery=items;
    main.innerHTML=heading('MADE HERE. KEPT HERE.','Output gallery','Images, videos and the files that travel with them.',`<button data-action="trash-list">Recovery bin</button><button data-action="refresh">↻ Refresh</button><button data-action="backup-selected" ${state.selectedFiles.size?'':'disabled'}>Back up selected</button><button class="primary" data-action="backup-all">Back up all outputs ↗</button>`)+
      `<div class="toolbar"><label class="search">⌕ <input data-search="gallery" aria-label="Search output files" value="${escape(state.query)}" placeholder="Search output filenames"></label><div class="segmented">${['all','image','video','file'].map(t=>`<button data-filter="${t}" class="${filter===t?'active':''}">${t==='all'?'All files':t+'s'}</button>`).join('')}</div><select aria-label="Sort gallery" data-sort><option value="date">Most recent</option><option value="size" ${state.sort==='size'?'selected':''}>Largest files</option></select></div>
      <div class="selection-bar"><label><input type="checkbox" data-select-all ${items.length&&items.every(f=>state.selectedFiles.has(f.id))?'checked':''}> Select all ${items.length} filtered files</label><span>${state.selectedFiles.size} selected · ${bytes(state.gallery.filter(f=>state.selectedFiles.has(f.id)).reduce((s,f)=>s+f.size,0))}</span></div>
      <div class="gallery-grid">${items.map(f=>`<article class="media-card"><label class="media-select"><input type="checkbox" data-file-check="${f.id}" ${state.selectedFiles.has(f.id)?'checked':''} aria-label="Select ${escape(f.path)}"></label><button class="media-main" data-media="${f.id}">${f.kind==='image'?`<img loading="lazy" src="${api.media(f.id)}" alt="${escape(f.path)}">`:`<div class="media-placeholder">${f.kind==='video'?'▷':'▤'}<small>${escape(f.path.split('.').pop().toUpperCase())}</small></div>`}<div class="media-copy"><strong>${escape(f.path)}</strong><span>${bytes(f.size)} <i>·</i> ${new Date(f.mtime_ns/1e6).toLocaleDateString()}</span></div></button><div class="card-footer"><button class="danger-text" data-delete-media="${f.id}" aria-label="Delete ${escape(f.path)}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/></svg>Delete</button></div></article>`).join('')||'<div class="empty"><span>▧</span><h2>Room for your next creation</h2><p>Generated files will appear here after refresh.</p></div>'}</div>`;
  }
  function renderSettings() {
    main.innerHTML=heading('YOUR TOOLS. YOUR CONTROL.','Workspace settings','Local by design, explicit about every change.')+`<div class="settings-grid"><section class="setting-card"><h2>Language</h2><label>Interface language<select data-language-select aria-label="Interface language"><option value="en">English</option><option value="fa">فارسی</option></select></label><p>Translate interface text only. Panels, cards and controls keep their positions.</p></section><section class="setting-card"><h2>Default Projects folder</h2><p>New captures and manual projects are saved here automatically. This archive stays on disk after uninstall.</p><p class="project-location">${escape(projects.root||'Not selected — you will be asked on first save.')}</p><button data-action="project-storage">Choose default folder</button><p class="small muted">Changing this location opens another archive; existing projects are not moved.</p></section><section class="setting-card"><h2>Private runtime</h2><p>All file work runs in M Tools’ own Python. Nothing is installed into ComfyUI’s Python environment.</p><button data-action="status">Inspect installation</button></section><section class="setting-card"><h2>Library location</h2><p>Keep the library inside M Tools, or choose a dedicated external folder before saving your first workflow. Its ownership is tracked for full uninstall.</p><button data-action="storage">Choose library folder</button></section><section class="setting-card"><h2>Library backup</h2><p>Export your saved workflow snapshots and metadata to a verified, independent folder or ZIP.</p><button data-action="library-backup">Back up library</button></section><section class="setting-card"><h2>Frontend compatibility</h2><p>Open M Tools using its sidebar icon below Templates. Closing the panel leaves the shortcut available.</p><span class="badge good">Sidebar shortcut</span></section><section class="setting-card danger-card"><h2>Uninstall M Tools</h2><p>Remove the plugin, private Python and all owned library data. Your models, original outputs and independent Projects archives stay in place. First restore or explicitly purge every file in the recovery bin.</p><button class="danger" data-action="uninstall">Review full uninstall</button></section></div><div class="design-credit">Design by Maisam Hosaini <span aria-hidden="true">|</span> <a href="https://storyeco.xyz" target="_blank" rel="noopener noreferrer">storyeco.xyz</a></div>`;
  }
  function modal(title, html, onSubmit) {
    const layer=$('.modal-layer');
    layer.innerHTML=`<dialog open aria-label="${escape(title)}"><form><div class="modal-heading"><h2>${escape(title)}</h2><button type="button" data-modal-close aria-label="Close dialog">×</button></div>${html}<p class="form-error" role="alert"></p></form></dialog>`;
    const dialog=layer.querySelector('dialog'), form=layer.querySelector('form');
    const previous=root.activeElement;
    const close=()=>{layer.innerHTML='';previous?.focus();};
    layer.querySelector('[data-modal-close]').onclick=close;
    dialog.addEventListener('keydown',e=>{
      if(e.key==='Escape'){e.preventDefault();close();}
      if(e.key==='Tab'){const inputs=[...dialog.querySelectorAll('button,input,textarea,select,a')].filter(x=>!x.disabled);const first=inputs[0],last=inputs.at(-1);if(e.shiftKey&&root.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&root.activeElement===last){e.preventDefault();first.focus();}}
    });
    form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('[type=submit]');if(button)button.disabled=true;try{await onSubmit(new FormData(form),form,close);}catch(e){form.querySelector('.form-error').textContent=e.message;}finally{if(button)button.disabled=false;}};
    queueMicrotask(()=>form.querySelector('input,button')?.focus());
    return {form,close};
  }
  async function coverData(file) {
    if(!file?.size)return null;
    if(file.size>10*1024*1024||!['image/png','image/jpeg','image/webp'].includes(file.type)) throw new Error('Cover must be PNG, JPEG or WebP, up to 10 MiB.');
    const bitmap=await createImageBitmap(file);
    if(bitmap.width>16384||bitmap.height>16384){bitmap.close();throw new Error('Cover dimensions are too large.');}
    const ratio=Math.min(1,1600/Math.max(bitmap.width,bitmap.height));
    const canvas=document.createElement('canvas');canvas.width=Math.round(bitmap.width*ratio);canvas.height=Math.round(bitmap.height*ratio);canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();return canvas.toDataURL('image/png');
  }
  async function edit(id) {
    const w=id?await call('workflow.get',{id}):null;
    modal(w?'Edit workflow':'Add a workflow',`<label>Title<input name="title" required maxlength="200" value="${escape(w?.title||'')}" placeholder="Give this workflow a name"></label><div class="two"><label>Graph source<select name="source">${w?'<option value="saved">Keep saved graph</option>':''}<option value="active">Current ComfyUI tab</option><option value="json" ${!integration.active?'selected':''}>Import workflow JSON</option></select></label><label>Workflow JSON<input type="file" name="json" accept=".json,application/json"></label></div><label>Description<textarea name="description" rows="3" maxlength="20000" placeholder="What does it make? What should you remember?">${escape(w?.description||'')}</textarea></label><label>Tags<input name="tags" value="${escape(w?.tags.join(', ')||'')}" placeholder="portrait, video, experimental"></label><label>Cover image · optional<input type="file" name="cover" accept="image/png,image/jpeg,image/webp"></label>${w?.cover?'<label class="inline-label"><input type="checkbox" name="remove-cover"> Remove current cover</label>':''}<div class="modal-footer"><span class="muted">A saved snapshot; never runs automatically.</span><button type="submit" class="primary">${w?'Save changes':'Add workflow'}</button></div>`,async(data,form,close)=>{
      let graph=w?.graph;
      if(data.get('source')==='active'){if(!integration.active)throw new Error('Current-tab capture is only available inside ComfyUI.');graph=await integration.active();}
      if(data.get('source')==='json'){const file=data.get('json');if(!file.size||file.size>20*1024*1024)throw new Error('Select a workflow JSON up to 20 MiB.');graph=JSON.parse(await file.text());}
      if(!Array.isArray(graph?.nodes))throw new Error('Use a ComfyUI workflow graph, not an API prompt.');
      const uploaded=await coverData(data.get('cover'));
      const item=await call('workflow.save',{title:data.get('title'),description:data.get('description'),tags:data.get('tags').split(',').map(s=>s.trim()).filter(Boolean),cover:uploaded||(data.get('remove-cover')?null:w?.cover)||null,graph,...(w?{id:w.id,expected_revision:w.revision}:{})});
      close();state.selected=item.id;await refresh();await select(item.id);
    });
  }
  async function startJob(kind,options={}) {
    const bar=$('.job');notice('');
    try {
      const {id}=await call('job.start',{kind,options,key:crypto.randomUUID()});state.job=id;bar.hidden=false;
      while(state.alive&&state.job===id) {
        const job=await call('job.get',{id});
        if(['complete','failed','cancelled'].includes(job.status)) {
          if(job.status==='complete'){await refresh();notice(job.result?.warnings?.length?`Saved with ${job.result.warnings.length} notes — select the project to review missing or unverified items.`:job.result?.requirements_complete===false?'Package copied and verified, with unresolved requirements.':`Completed${job.result?.destination?' · '+job.result.destination:''}`);}
          else notice(job.error||job.status,true);
          break;
        }
        bar.innerHTML=`<div><strong>${escape(kind)} · ${escape(job.status)}</strong><span>${Math.round(job.progress*100)}%</span><button data-action="cancel-job">Cancel</button></div><progress max="1" value="${job.progress}"></progress>`;
        await new Promise(r=>setTimeout(r,700));
      }
    } finally {state.job=null;bar.hidden=true;bar.innerHTML='';}
  }
  function packageDialog(kind,id=null,files=null) {
    const {form}=modal(kind==='export'?'Export workflow':kind==='library.backup'?'Back up library':'Back up outputs',`${kind==='export'?'<label>Export format<select name="format"><option value="json">Workflow JSON only</option><option value="folder">Folder with models</option><option value="zip">ZIP with models</option></select></label>':'<label>Format<select name="format"><option value="folder">Copy into a new folder</option><option value="zip">ZIP archive</option></select></label>'}<div data-destination><label>New destination path<div class="destination-row"><input name="destination" placeholder="D:\\Backups\\MTools-export" autocomplete="off"><button type="button" data-choose-destination>Choose destination…</button></div></label></div><p class="small muted">JSON downloads through your browser. For folder/ZIP exports, choose or enter a new absolute path outside ComfyUI and output/model roots. The parent folder must exist. Existing destinations are never overwritten.</p>${kind==='export'?'<label class="inline-label"><input type="checkbox" name="incomplete"> Allow a clearly labeled package with unresolved dependencies</label>':`<p class="muted">${files?`${files.length} selected files`:'All files, independent of gallery filters'} · Originals stay in place.</p>`}<div class="modal-footer"><span>Copies are verified with SHA-256.</span><button type="submit" class="primary">Export</button></div>`,async(data,form,close)=>{
      if(data.get('format')==='json'){const w=await call('workflow.get',{id});download(`${w.title.replace(/[<>:"/\\|?*]/g,'_')}.json`,JSON.stringify(w.graph,null,2));close();return;}
      if(!data.get('destination').trim())throw new Error('A destination is required.');
      if(kind==='export'&&!data.get('incomplete')) {
        const check=await call('workflow.check',{id});
        if(check.status!=='complete')throw new Error('Requirements need attention: '+[...check.models.filter(m=>m.status!=='found'),...check.custom_nodes.filter(n=>n.status!=='loaded'),...check.unresolved].map(n=>n.name||n.type).join(', ')+'. Review details or explicitly allow an incomplete package.');
      }
      const options={destination:data.get('destination').trim(),zip:data.get('format')==='zip',...(id?{id}:{}),...(files?{files}:{}) ,allow_incomplete:!!data.get('incomplete')};close();await startJob(kind,options);
    });
    const format=form.elements.format;
    const update=()=>{form.querySelector('[data-destination]').hidden=format.value==='json';};
    format.addEventListener('change',update);update();
    const panel=document.createElement('section');panel.className='destination-browser';panel.hidden=true;
    form.querySelector('[data-destination]').append(panel);
    let location=null;
    async function browse(path='') {
      panel.hidden=false;
      panel.innerHTML='<p role="status">Loading folders…</p><button type="button" data-picker-close>Cancel</button>';
      panel.querySelector('[data-picker-close]').onclick=()=>{panel.hidden=true;};
      try {
        location=await call('destination.browse',{path,mode:format.value});
        panel.innerHTML=`<div class="picker-heading"><strong>Choose destination folder</strong><button type="button" data-picker-close aria-label="Close folder chooser">×</button></div><div class="destination-row"><button type="button" data-drives>Drives</button><button type="button" data-up ${location.path?'':'disabled'}>↑ Up</button><input aria-label="Browse folder path" value="${escape(location.path)}" placeholder="Select a drive below"><button type="button" data-go>Go</button></div><div class="folder-choices">${location.folders.map(f=>`<button type="button" data-folder="${escape(f.path)}">▱ ${escape(f.name)}</button>`).join('')||'<p class="muted">No subfolders. You can use this folder.</p>'}</div><p class="small muted">A new ${format.value==='zip'?'ZIP archive':'export folder'} will be created inside the selected folder.</p><button type="button" class="primary" data-use-folder ${location.path?'':'disabled'}>Use this folder</button>`;
        panel.querySelector('[data-picker-close]').onclick=()=>{panel.hidden=true;};
        panel.querySelector('[data-drives]').onclick=()=>browse();
        panel.querySelector('[data-up]').onclick=()=>browse(location.parent);
        panel.querySelector('[data-go]').onclick=()=>browse(panel.querySelector('input').value);
        panel.querySelector('input').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();void browse(e.target.value);}};
        panel.querySelectorAll('[data-folder]').forEach(button=>button.onclick=()=>browse(button.dataset.folder));
        panel.querySelector('[data-use-folder]').onclick=()=>{form.elements.destination.value=location.destination;panel.hidden=true;};
      } catch(error){panel.innerHTML=`<p class="form-error">${escape(error.message)}</p><button type="button" data-retry>Back to drives</button>`;panel.querySelector('[data-retry]').onclick=()=>browse();}
    }
    format.addEventListener('change',()=>{panel.hidden=true;});
    form.querySelector('[data-choose-destination]').onclick=()=>browse();
  }
  function selectedFiles() {return state.gallery.filter(f=>state.selectedFiles.has(f.id)).map(f=>({id:f.id,version:f.signature}));}
  function confirmAction(title,description,action,button='Confirm') {modal(title,`<p>${escape(description)}</p><div class="modal-footer"><span></span><button type="submit" class="danger">${escape(button)}</button></div>`,async(_,f,close)=>{await action();close();await refresh();});}
  async function showTrash() {
    const items=await call('gallery.trash.list');
    const {form,close}=modal('Recovery bin',`<p class="muted">Files here still occupy disk space. Permanent deletion cannot be undone.</p>${items.map(i=>`<div class="trash-row"><div><strong>${escape(i.original)}</strong><small>${bytes(i.signature[0])} · ${i.payload_exists?'Recoverable':'Journal only; review needed'}</small></div><button type="button" data-restore="${i.id}">Restore</button><button type="button" class="danger-text" data-purge="${i.id}">Delete permanently</button></div>`).join('')||'<p>The recovery bin is empty.</p>'}`,()=>{});
    form.addEventListener('click',e=>safe(async()=>{const b=e.target.closest('button');if(b?.dataset.restore){await call('gallery.restore',{id:b.dataset.restore});close();await showTrash();}if(b?.dataset.purge){const id=b.dataset.purge;close();confirmAction('Permanently delete this file?','This removes the recovery copy and frees its disk space. This action cannot be undone.',()=>call('gallery.purge',{id,confirmation:'PERMANENTLY DELETE'}),'Delete permanently');}}));
  }
  const actions={
    'dismiss-notice':()=>notice(''),
    close:()=>integration.close?.(),add:()=>edit(),refresh,scan:()=>startJob('scan'),
    deselect:()=>{state.selected=null;state.detail=null;render();},check:()=>select(state.selected),
    open:async()=>{if(!integration.openWorkflow)throw new Error('Opening a graph is available inside ComfyUI.');await integration.openWorkflow(state.detail.graph,state.detail.title);notice('Opened in a new tab. Your other workflow tabs are preserved.');},
    'toggle-deleted':async()=>{state.deleted=!state.deleted;state.selected=null;state.detail=null;await refresh();},
    'delete-workflow':()=>confirmAction(state.detail.deleted?'Restore workflow?':'Remove workflow?',state.detail.deleted?'Return this workflow to the library.':'The workflow moves to library recovery. Model files are untouched.',async()=>{await call(state.detail.deleted?'workflow.restore':'workflow.delete',{id:state.detail.id,expected_revision:state.detail.revision});state.selected=null;state.detail=null;}),
    revision:()=>modal('Restore an earlier revision',`<p>Restore a previous saved snapshot as a new revision. Your current revision stays in history.</p><label>Revision (current: ${state.detail.revision})<input type="number" name="revision" min="1" max="${state.detail.revision}" required></label><button type="submit" class="primary">Restore as a new revision</button>`,async(d,f,c)=>{await call('workflow.restore',{id:state.detail.id,expected_revision:state.detail.revision,revision:Number(d.get('revision'))});c();await refresh();await select(state.selected);}),
    'report-csv':async()=>download('mtools-report.csv',(await call('report.export',{format:'csv'})).text,'text/csv;charset=utf-8'),
    'report-json':async()=>download('mtools-report.json',(await call('report.export')).text),
    'backup-all':()=>packageDialog('backup'),'backup-selected':()=>packageDialog('backup',null,selectedFiles()),
    'library-backup':()=>packageDialog('library.backup'),'trash-list':showTrash,
    'cancel-job':()=>call('job.cancel',{id:state.job}),
    'project-storage':()=>projects.configure(()=>{renderSettings();notice('Default Projects folder saved.');},true),
    storage:()=>modal('Choose library location','<p>Choose a new, dedicated folder outside ComfyUI, models and outputs. Its parent must exist. This can be set before the first saved workflow.</p><label>New library path<input name="destination" required placeholder="D:\\Libraries\\MTools"></label><p class="small muted">Full uninstall will remove this owned library folder too. Keep independent backups elsewhere.</p><button type="submit" class="primary">Use this folder</button>',async(d,f,c)=>{const result=await call('storage.configure',{destination:d.get('destination')});c();notice(`Library location: ${result.library_path}`);}),
    status:async()=>{const s=await call('status');modal('Installation details',`<pre>${escape(JSON.stringify(s,null,2))}</pre>`,()=>{});},
    uninstall:async()=>{const p=await call('uninstall.plan');modal('Full uninstall',`<p>${escape(p.instructions)}</p><p class="badge ${p.blocked?'warn':'good'}">${p.trash_count} files in recovery bin</p><label>Owned folder<input readonly value="${escape(p.plugin)}"></label><p class="small">Save your open ComfyUI tabs before closing the host.</p><p>After closing ComfyUI, right-click <strong>scripts/Uninstall.ps1</strong> → Run with PowerShell. It stages an independent cleaner and confirms the exact folder before removal.</p><p class="muted">Status: ${p.blocked?'Blocked by recovery-bin contents':'Ready for offline cleanup; not yet uninstalled'}</p>`,()=>{});}
  };
  root.addEventListener('click',e=>safe(async()=>{
    const b=e.target.closest('button,a');if(!b)return;
    if(b.dataset.tab){state.tab=b.dataset.tab;state.query='';render();await refresh();}
    else if(b.dataset.action)await actions[b.dataset.action]?.();
    else if(b.dataset.select)await select(b.dataset.select);
    else if(b.dataset.openWorkflow){
      b.disabled=true;
      try {
        if(!integration.openWorkflow)throw new Error('Opening a graph is available inside ComfyUI.');
        const workflow=await call('workflow.get',{id:b.dataset.openWorkflow});
        await integration.openWorkflow(workflow.graph,workflow.title);
        notice('Opened in a new tab. Your other workflow tabs are preserved.');
      } finally {b.disabled=false;}
    }
    else if(b.dataset.edit)await edit(b.dataset.edit);
    else if(b.dataset.export)packageDialog('export',b.dataset.export);
    else if(b.dataset.copy){await navigator.clipboard.writeText(b.dataset.copy);notice('Path copied.');}
    else if(b.dataset.filter){state.galleryFilter=b.dataset.filter;render();}
    else if(b.dataset.deleteMedia){
      const file=state.gallery.find(f=>f.id===b.dataset.deleteMedia);
      modal('Permanently delete this output?',`<p>${escape(file.path)}</p><p>This deletes the original file from ComfyUI outputs and its Assets listing. It cannot be undone.</p><div class="modal-footer"><span></span><button type="submit" class="danger">Delete permanently</button></div>`,async(d,f,close)=>{
        const result=await call('gallery.delete',{id:file.id,version:file.signature,confirmation:'PERMANENTLY DELETE'});
        close();await refresh();notice(result.warning||'File permanently deleted.',!!result.warning);
      });
    }
    else if(b.dataset.media){const f=state.gallery.find(x=>x.id===b.dataset.media);const {form}=modal(f.path,`${f.kind==='image'?`<img class="media-preview" src="${api.media(f.id)}" alt="${escape(f.path)}">`:f.kind==='video'?`<video class="media-preview" src="${api.media(f.id)}" controls preload="metadata"></video><p class="small muted">Playback depends on browser codec support. Use Open file if unavailable.</p>`:'<p>Preview is not available for this format.</p>'}<p>${bytes(f.size)}</p><div class="two"><button type="button" data-external="open">Open file</button><button type="button" data-external="reveal">Open in folder</button></div>`,()=>{});form.querySelectorAll('[data-external]').forEach(x=>x.onclick=()=>safe(()=>call('gallery.open',{id:f.id,reveal:x.dataset.external==='reveal'})));}
  }),{signal:signal.signal});
  root.addEventListener('input',e=>{if(e.target.dataset.search){const input=e.target,start=input.selectionStart;state.query=input.value;render();const next=$('[data-search]');next?.focus();next?.setSelectionRange(start,start);}},{signal:signal.signal});
  root.addEventListener('change',e=>{const el=e.target;if(el.dataset.fileCheck){el.checked?state.selectedFiles.add(el.dataset.fileCheck):state.selectedFiles.delete(el.dataset.fileCheck);render();}if(el.hasAttribute('data-select-all')){state.filteredGallery.forEach(f=>el.checked?state.selectedFiles.add(f.id):state.selectedFiles.delete(f.id));render();}if(el.hasAttribute('data-sort')){state.sort=el.value;render();}},{signal:signal.signal});
  const stopLocalization=localize(root);
  render();void safe(async()=>{await refresh();if(integration.captureOnOpen)await projects.capture();});
  host.addEventListener('mtools-capture-project',()=>safe(async()=>{state.tab='projects';await refresh();await projects.capture();}),{signal:signal.signal});
  return ()=>{state.alive=false;signal.abort();stopLocalization();root.innerHTML='';};
}
