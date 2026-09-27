const e = (v='')=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const projectCoverNames=['mint','lavender','amber','arctic'];
const projectCovers=projectCoverNames.map(name=>new URL(`./project-covers/${name}.png`,import.meta.url).href);

export class ProjectPanel {
  constructor(main, api, integration, helpers){
    this.main=main;this.api=api;this.integration=integration;Object.assign(this,helpers);this.items=[];this.selected=null;this.root=null;
    main.addEventListener('click',event=>{
      const button=event.target.closest('[data-project-action]');if(!button)return;
      void (async()=>{try{await this.action(button.dataset.projectAction,button.dataset.id);}catch(error){this.notice(error.message,true);}})();
    });
  }
  async refresh(){const data=await this.api.call('projects');this.items=data.items;this.root=data.root;this.errors=data.errors;if(this.selected)this.detail=await this.api.call('project.get',{id:this.selected});this.render();}
  cover(p){if(this.api.demo&&p.cover)return p.cover;return p.cover_path?this.api.projectMedia(p.id,p.cover_path):projectCovers[(parseInt(p.id.slice(-2),16)||0)%4];}
  render(){
    const d=this.detail;
    this.main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">INPUT. PROCESS. RESULT.</div><h1>Projects</h1><p>Your production records, stored independently.</p></div><div class="actions"><button data-project-action="location">Archive location</button><button data-project-action="import">Import</button><button data-project-action="new">＋ New</button><button class="primary" data-project-action="capture">Save active tab</button></div></div><p class="project-location muted">${this.root?e(this.root)+' · Preserved when M Tools is uninstalled':'Choose an independent archive folder to get started.'}</p>${this.errors?.length?`<p class="form-error">${this.errors.length} project folders could not be read.</p>`:''}<div class="library-layout"><div class="cards">${this.items.map(p=>`<article class="workflow-card ${this.selected===p.id?'selected':''}"><button class="card-main" data-project-action="select" data-id="${p.id}"><img class="cover" src="${e(this.cover(p))}" alt="${e(p.title)}"><div class="card-copy"><div class="card-title">${e(p.title)}</div><p>${e(p.description||'Production record')}</p><small>${p.file_count} files · ${this.bytes(p.bytes)}</small></div></button><div class="card-footer"><span>${new Date(p.created_at*1000).toLocaleDateString()}</span><div><button data-project-action="edit" data-id="${p.id}">Edit</button><button data-project-action="folder" data-id="${p.id}">Open folder</button></div></div></article>`).join('')||'<div class="empty"><h2>Keep the story behind your result</h2><p>Save the active tab, create a record manually, or import a project folder or ZIP.</p></div>'}</div><aside class="detail">${d?`<div class="eyebrow">PRODUCTION RECORD</div><img class="cover large" src="${e(this.cover(d))}" alt="${e(d.title)}"><h2>${e(d.title)}</h2><p>${e(d.description)}</p><div class="detail-actions"><button class="primary" data-project-action="open" data-id="${d.id}">Open workflow in new tab</button><div class="two"><button data-project-action="json" data-id="${d.id}">Workflow JSON</button><button data-project-action="export" data-id="${d.id}">Export project</button></div><button data-project-action="edit" data-id="${d.id}">Edit details</button></div><h3>Prompt</h3><pre class="project-prompt" tabindex="0" aria-label="Project prompt">${e(d.prompt||'No prompt text recorded.')}</pre><div class="prompt-actions"><button data-project-action="copy-prompt" data-id="${d.id}" title="Copy entire prompt" aria-label="Copy entire prompt" ${d.prompt?'':'disabled'}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg></button><span class="prompt-copy-status" role="status"></span></div><h3>References</h3>${this.files(d,'references')}<h3>Final outputs</h3>${this.files(d,'outputs')}<details><summary>Workflow data</summary><pre>${e(JSON.stringify(d.capture||{},null,2))}</pre><p>Node settings are preserved in workflow.json.</p></details>${(d.warnings||[]).map(w=>`<p class="project-warning">${e(w)}</p>`).join('')}`:'<div class="empty"><h2>A closer look</h2><p>Select a project to view its references, prompt, workflow and final outputs.</p></div>'}</aside></div>`;
  }
  files(d,role){return d.files.filter(f=>f.role===role).map(f=>{
    const url=this.api.projectMedia(d.id,f.path),ext=f.path.split('.').pop().toLowerCase();
    const preview=['png','jpg','jpeg','webp','gif'].includes(ext)?`<img loading="lazy" class="project-media" src="${e(url)}" alt="${e(f.name)}">`:['mp4','webm'].includes(ext)?`<video class="project-media" controls preload="metadata" src="${e(url)}"></video>`:['mp3','wav','ogg'].includes(ext)?`<audio controls preload="metadata" src="${e(url)}"></audio>`:'';
    return `<div class="project-file">${preview}<a href="${e(this.api.projectMedia(d.id,f.path,true))}" download>${e(f.name)}</a><small>${this.bytes(f.size)}</small></div>`;
  }).join('')||'<p class="muted">None recorded.</p>';}
  folderBrowser(form,inputName,newFolder=false){
    const panel=document.createElement('div');panel.className='destination-browser';panel.hidden=true;form.querySelector(`[name=${inputName}]`).parentElement.after(panel);
    let current='';let revision=0;
    const browse=async path=>{const request=++revision;panel.hidden=false;panel.innerHTML='<p>Loading folders…</p>';try{
      const data=await this.api.call('destination.browse',{path});if(request!==revision)return;current=data.path;
      panel.innerHTML=`<div class="destination-row"><button type="button" data-drives>Drives</button><button type="button" data-up>↑ Up</button><input aria-label="Browse project folder" value="${e(current)}"><button type="button" data-go>Go</button></div><div class="folder-choices">${data.folders.map(f=>`<button type="button" data-path="${e(f.path)}">▱ ${e(f.name)}</button>`).join('')}</div><button type="button" data-use ${current?'':'disabled'}>Use this folder</button> <button type="button" data-cancel>Cancel</button>`;
      panel.querySelector('[data-drives]').onclick=()=>browse('');panel.querySelector('[data-up]').onclick=()=>browse(data.parent);
      panel.querySelector('[data-go]').onclick=()=>browse(panel.querySelector('input').value);
      panel.querySelector('input').onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();void browse(event.target.value);}};
      panel.querySelectorAll('[data-path]').forEach(b=>b.onclick=()=>browse(b.dataset.path));
      panel.querySelector('[data-cancel]').onclick=()=>{revision++;panel.hidden=true;};
      panel.querySelector('[data-use]').onclick=()=>{form.elements[inputName].value=current+(newFolder?'/MTools Projects':'');panel.hidden=true;};
    }catch(error){panel.innerHTML=`<p class="form-error">${e(error.message)}</p><button type="button">Back to drives</button>`;panel.querySelector('button').onclick=()=>browse('');}};
    form.querySelector('[data-browse]').onclick=()=>browse('');
  }
  configure(after,stayOnSettings=false){
    const {form}=this.modal('Independent Projects folder',`<p>Choose a new archive folder or an existing M Tools Projects archive. It stays on disk when M Tools is uninstalled.</p><label>Archive path<input name="destination" required value="${e(this.root||'')}"></label><button type="button" data-browse>Choose folder…</button><div class="modal-footer"><span>Existing projects are not moved.</span><button type="submit" class="primary">Use archive</button></div>`,async(data,f,close)=>{const result=await this.api.call('projects.configure',{destination:data.get('destination')});this.root=result.path;this.selected=null;this.detail=null;close();if(!stayOnSettings)await this.refresh();if(after)await after();});
    this.folderBrowser(form,'destination',true);
  }
  async uploadFiles(form){
    const uploads=[];
    for(const role of ['references','outputs'])for(const file of form.elements[role]?.files||[]){this.notice(`Uploading ${file.name}…`);uploads.push({token:await this.api.upload(file),name:file.name,role});}
    return uploads;
  }
  async capture(){
    if(!this.root){this.configure(()=>this.capture());return;}
    if(!this.integration.snapshot)throw new Error('Active-tab capture is only available inside ComfyUI.');
    const snapshot=await this.integration.snapshot();
    const capture=await this.api.call('project.capture',{graph:snapshot.workflow,prompt:snapshot.output});
    await this.startJob('project.save',{title:snapshot.title||'Captured project',graph:snapshot.workflow,prompt:capture.prompt_text,capture});await this.refresh();
  }
  async editor(id){
    if(!this.root){this.configure(()=>this.editor(id));return;}
    const p=id?await this.api.call('project.get',{id}):null;
    this.modal(p?'Edit project':'New project',`<label>Title<input name="title" required maxlength="200" value="${e(p?.title||'')}"></label><label>Description<textarea name="description">${e(p?.description||'')}</textarea></label><label>Prompt<textarea name="prompt" rows="4">${e(p?.prompt||'')}</textarea></label>${p?'<label>Add references<input name="references" type="file" multiple></label><label>Add final outputs<input name="outputs" type="file" multiple></label>':`<label>Workflow<select name="source"><option value="active">Current tab</option><option value="json">Import JSON</option><option value="empty">No workflow yet</option></select></label><label>Workflow JSON<input name="graph" type="file" accept=".json"></label><label>References<input name="references" type="file" multiple></label><label>Final outputs<input name="outputs" type="file" multiple></label>`}<label>Cover image · optional<input type="file" name="cover" accept="image/png,image/jpeg,image/webp"></label><div class="modal-footer"><span>${p?'Original workflow and capture data are retained.':'Only media and data are archived.'}</span><button class="primary" type="submit">Save project</button></div>`,async(data,form,close)=>{
      const cover=await this.coverData(data.get('cover'));
      const values={title:data.get('title'),description:data.get('description'),prompt:data.get('prompt'),cover};
      if(p){const uploads=await this.uploadFiles(form);close();await this.startJob('project.update',{...values,id,expected_updated_at:p.updated_at,uploads});await this.refresh();return;}
      let graph={nodes:[],links:[]};
      if(data.get('source')==='active'){if(!this.integration.active)throw new Error('Current tab is unavailable');graph=await this.integration.active();}
      if(data.get('source')==='json'){const file=data.get('graph');if(!file.size||file.size>20*1024**2)throw new Error('Choose a workflow JSON up to 20 MiB');graph=JSON.parse(await file.text());}
      const uploads=await this.uploadFiles(form);close();await this.startJob('project.save',{...values,graph,uploads});await this.refresh();
    });
  }
  importProject(){
    if(!this.root){this.configure(()=>this.importProject());return;}
    const {form}=this.modal('Import project',`<p>Import a M Tools project folder or ZIP. Files are copied into this archive; the source stays intact.</p><label>Project folder<input name="path"></label><button type="button" data-browse>Choose folder…</button><label>Or project ZIP<input name="zip" type="file" accept=".zip"></label><button type="submit" class="primary">Import</button>`,async(data,f,close)=>{const zip=data.get('zip');const options=zip.size?{token:await this.api.upload(zip)}:{path:data.get('path')};if(!options.path&&!options.token)throw new Error('Choose a project folder or ZIP');close();await this.startJob('project.import',options);await this.refresh();});this.folderBrowser(form,'path');
  }
  exportProject(id){
    const {form}=this.modal('Export project',`<p>Export this dossier, including references, outputs and JSON. No model files.</p><label>New ZIP destination<input name="path" required placeholder="D:/Backups/project.zip"></label><button type="button" data-browse>Choose parent folder…</button><button class="primary" type="submit">Export ZIP</button>`,async(data,f,close)=>{let destination=data.get('path');if(!destination.toLowerCase().endsWith('.zip'))destination=destination.replace(/[\\/]$/,'')+'/MTools-project-'+Date.now()+'.zip';close();await this.startJob('project.export',{id,destination});});this.folderBrowser(form,'path');
  }
  async action(action,id){
    if(action==='copy-prompt'){
      const record=this.detail?.id===id?this.detail:await this.api.call('project.get',{id});
      await navigator.clipboard.writeText(record.prompt||'');
      const status=this.main.querySelector('.prompt-copy-status');if(status){status.textContent='Copied';setTimeout(()=>{if(status.isConnected)status.textContent='';},2500);}
      return;
    }
    if(action==='location')return this.configure();if(action==='capture')return this.capture();if(action==='new')return this.editor();if(action==='import')return this.importProject();if(action==='edit')return this.editor(id);if(action==='export')return this.exportProject(id);
    if(action==='select'){this.selected=id;this.detail=await this.api.call('project.get',{id});this.render();}
    if(action==='folder')await this.api.call('project.reveal',{id});
    if(action==='json'||action==='open'){const p=await this.api.call('project.get',{id});if(action==='json')this.download('workflow.json',JSON.stringify(p.graph,null,2));else{if(!this.integration.openWorkflow)throw new Error('Open inside ComfyUI');await this.integration.openWorkflow(p.graph,p.title);this.notice('Opened workflow in a new tab.');}}
  }
}
