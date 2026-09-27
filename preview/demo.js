import {mount} from '../web/ui.js';
const folders='audio_encoders background_removal checkpoints clip clip_vision configs controlnet detection diffusers diffusion_models embeddings frame_interpolation geometry_estimation gligen hypernetworks latent_upscale_models loras model_patches optical_flow photomaker sam2 style_models text_encoders unet upscale_models vae vae_approx'.split(' ');
const GiB=1073741824;
const examples=[['Editorial portrait','A considered portrait pipeline with soft light and a clean editorial finish.',['portrait','SDXL'],12],['Product studio','Controlled lighting and crisp surfaces for product explorations.',['product','studio'],5],['Motion studies','A starting point for short cinematic motion experiments.',['video','motion'],8],['Quiet landscapes','Natural textures, open space and atmospheric depth.',['landscape','Flux'],3],['Detail upscaler','A final pass for texture, clarity and larger outputs.',['upscale','utility'],4],['Material explorations','Explore tactile shapes, materials and subtle lighting.',['material','3D'],6]];
let library=examples.map(([title,description,tags,revision],i)=>({id:String(i+1).padStart(32,'0'),title,description,tags,revision,updated_at:Date.now()/1000-i*1000,graph:{version:0.4,nodes:[],links:[]},deleted:false,cover:null}));
const report={portable_bytes:186.4*GiB,comfy_bytes:174.1*GiB,portable_unique_bytes:186.4*GiB,models_bytes:142.8*GiB,scanned_at:Date.now()/1000,measurement:'Logical file sizes · links excluded · sample data',external:[],errors:[],groups:folders.map((name,i)=>{const names={checkpoints:['sd_xl_base_1.0.safetensors','studioMix_v3.safetensors'],clip:['clip_l.safetensors'],clip_vision:['clip_vision_h.safetensors'],unet:['flux1-dev.safetensors'],text_encoders:['t5xxl_fp16.safetensors'],vae:['ae.safetensors'],loras:['editorial-light.safetensors'],controlnet:['depth-controlnet.safetensors'],upscale_models:['4x-UltraSharp.pth']};const files=(names[name]||[]).map((n,j)=>({path:`${name}/${n}`,absolute_path:`D:\ComfyUI_windows_portable\ComfyUI\models\${name}\${n}`,size:(i+1)*.31*GiB,source_url:null}));return {name,files,exists:true,count:files.length,size:files.reduce((s,f)=>s+f.size,0)};})};
let jobs={},trash=[],deleted=new Set();
const media=Array.from({length:12},(_,i)=>({id:'media'+i,path:`${i<6?'portraits':'studies'}/ComfyUI_${String(i+1).padStart(5,'0')}${i===3?'.mp4':'.png'}`,size:(i+2)*1834532,mtime_ns:(Date.now()-i*3600000)*1e6,kind:i===3?'video':'image',signature:[(i+2)*1834532,i,0,i]}));
let projectRoot='D:/Creative Archive/MTools Projects';
let projects=['Product film','Portrait study','Material exploration','Motion concept'].map((title,i)=>({id:String(i).padStart(32,'0'),title,description:'Sample production record — references, prompt and final result.',prompt:'Soft studio light, considered composition, gentle camera movement.',created_at:Date.now()/1000,updated_at:Date.now()/1000,files:[],file_count:0,bytes:0,graph:{nodes:[],links:[]},capture:{source:'sample data'},warnings:[],cover_path:null}));
const api={demo:true,projectMedia(){return "";},async upload(){return crypto.randomUUID().replaceAll("-","");},media(id){const n=Number(id.replace('media',''));const colors=[['#36483d','#c7e0b4'],['#42364b','#bca0d4'],['#4d3c32','#d9b99a'],['#2f4149','#97c0ce']][n%4];const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480"><defs><radialGradient id="g" cx=".3" cy=".2"><stop stop-color="${colors[1]}"/><stop offset="1" stop-color="${colors[0]}"/></radialGradient></defs><rect width="640" height="480" fill="${colors[0]}"/><ellipse cx="320" cy="255" rx="${100+n*4}" ry="155" fill="url(#g)"/><text x="24" y="451" fill="#ffffff88" font-family="sans-serif" font-size="12" letter-spacing="3">M TOOLS • SAMPLE OUTPUT</text></svg>`;return 'data:image/svg+xml,'+encodeURIComponent(svg);},async call(method,p={}){
  await new Promise(r=>setTimeout(r,80));
  if(method==='projects')return {root:projectRoot,items:structuredClone(projects),errors:[]};
  if(method==='projects.configure'){projectRoot=p.destination;return {path:projectRoot};}
  if(method==='project.get')return structuredClone(projects.find(x=>x.id===p.id));
  if(method==='project.edit'){Object.assign(projects.find(x=>x.id===p.id),p);return {id:p.id};}
  if(method==='project.reveal')throw new Error('Preview only: no local folders are opened.');
  if(method==='project.capture')return {prompt_text:'Sample prompt',files:[],metadata:{source:'preview'},warnings:[]};
  if(method==='workflows')return structuredClone(library.filter(w=>w.deleted===!!p.deleted));
  if(method==='workflow.get')return structuredClone(library.find(w=>w.id===p.id));
  if(method==='workflow.check')return {status:'needs_attention',checked_at:Date.now()/1000,models:[{name:'sd_xl_base_1.0.safetensors',target:'checkpoints/sd_xl_base_1.0.safetensors',status:'found'},{name:'editorial-light.safetensors',category:'loras',status:'missing'}],custom_nodes:[],unresolved:[],notice:'Sample status. Availability checks never execute a workflow.'};
  if(method==='workflow.save'){const old=library.find(w=>w.id===p.id);const w={...p,id:p.id||crypto.randomUUID().replaceAll('-',''),revision:(old?.revision||0)+1,updated_at:Date.now()/1000,deleted:false};library=library.filter(x=>x.id!==w.id);library.unshift(w);return structuredClone(w);}
  if(method==='workflow.delete'||method==='workflow.restore'){const w=library.find(x=>x.id===p.id);w.deleted=method==='workflow.delete';w.revision++;return w;}
  if(method==='report')return report;
  if(method==='report.export')return {text:JSON.stringify(report,null,2)};
  if(method==='gallery')return {files:media.filter(f=>!deleted.has(f.id)&&!trash.some(t=>t.media_id===f.id)),errors:[]};
  if(method==='destination.browse')return {path:p.path||'',parent:'',folders:p.path?[]:[{name:'D:/',path:'D:/'}],destination:'D:/MTools-preview'+(p.mode==='zip'?'.zip':'')};
  if(method==='gallery.delete'){deleted.add(p.id);return {deleted:p.id};}
  if(method==='gallery.trash.list')return trash;
  if(method==='gallery.trash'){for(const s of p.files){const f=media.find(x=>x.id===s.id);trash.push({id:s.id,media_id:s.id,original:f.path,signature:f.signature,payload_exists:true});}return p.files.map(f=>({id:f.id,ok:true}));}
  if(method==='gallery.restore'||method==='gallery.purge'){trash=trash.filter(x=>x.id!==p.id);return {};}
  if(method==='gallery.open')throw new Error('Design preview: no local files are opened.');
  if(method==='job.start'){if(p.kind==='project.import')throw new Error('Preview only. Import a real project inside ComfyUI.');if(p.kind==='project.update'){Object.assign(projects.find(x=>x.id===p.options.id),p.options,{updated_at:Date.now()/1000});}if(p.kind==='project.save'){projects.unshift({...p.options,id:crypto.randomUUID().replaceAll('-',''),created_at:Date.now()/1000,updated_at:Date.now()/1000,files:[],file_count:0,bytes:0,warnings:[],cover_path:null});}const id=crypto.randomUUID();jobs[id]={status:'running',progress:0,result:{destination:p.options?.destination||null}};return {id};}
  if(method==='job.get'){const j=jobs[p.id];j.progress=Math.min(1,j.progress+.34);if(j.progress===1)j.status='complete';return j;}
  if(method==='job.cancel'){jobs[p.id].status='cancelled';return {};}
  if(method==='status')return {preview:true,notice:'Sample data only. No ComfyUI process, model or Python environment is accessed.'};
  if(method==='uninstall.plan')return {plugin:'Preview only — nothing installed',blocked:trash.length>0,trash_count:trash.length,instructions:'The real uninstaller validates ownership and waits for you to close ComfyUI. This preview never deletes anything.'};
  throw new Error('Not available in this preview');
}};
await mount(document.getElementById('app'),api,{initialTab:location.hash==='#projects'?'projects':'workflows',active:async()=>({version:.4,nodes:[],links:[]}),openWorkflow:async()=>{throw new Error('Preview only. In ComfyUI this creates a new tab, preserving the current graph.');}});
