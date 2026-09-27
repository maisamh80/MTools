import {translate,getLanguage} from './i18n.js';
import {app} from '../../scripts/app.js';
import {Client} from './client.js';
import {mount} from './ui.js';

let closePanel;
let opening = false;
let panelElement;
async function open(capture=false) {
  capture=capture===true;
  if(closePanel){if(capture)panelElement?.dispatchEvent(new Event('mtools-capture-project'));return;}
  if(opening)return;
  opening = true;
  const element = document.createElement('div');panelElement=element;
  document.body.append(element);
  const client = new Client();
  try {
  closePanel = await mount(element, client, {
    initialTab:capture?'projects':'workflows',captureOnOpen:capture,
    snapshot:async()=>({...await app.graphToPrompt(),title:app.extensionManager.workflow.activeWorkflow?.filename||'Captured project'}),
    active: async () => (await app.graphToPrompt()).workflow,
    openWorkflow: async (graph, name) => {
      const workflow = app.extensionManager?.workflow;
      if (!workflow?.createNewTemporary || !workflow?.openWorkflow)
        throw new Error('This ComfyUI frontend does not expose the supported new-tab API. Your current graph was not changed.');
      const tab = workflow.createNewTemporary(`${name}.json`, structuredClone(graph));
      await app.loadGraphData(structuredClone(graph), true, true, tab);
    },
    close: () => { closePanel?.(); closePanel = undefined; element.remove(); client.clearSession().catch(()=>{}); }
  });
  } finally { opening = false; }
}

app.registerExtension({
  name: 'MTools.Library',
  setup() {
    const manager = app.extensionManager;
    if(!document.getElementById('mtools-save-project')){
      const button=document.createElement('button');button.id='mtools-save-project';button.title='Save to M Tools Projects';button.setAttribute('aria-label','Save to M Tools Projects');
      button.style.cssText='display:flex;align-items:center;justify-content:center;height:34px;align-self:center;margin-block:auto;padding:0 10px;gap:7px;white-space:nowrap;color:#d5f9df;font:500 12px Inter,Segoe UI,sans-serif;border:1px solid #405449;border-radius:7px;background:#26372c;cursor:pointer';
      const icon=document.createElement('img');icon.src=new URL('./MTool.svg',import.meta.url).href;icon.style.cssText='width:22px;height:22px';icon.alt='';const label=document.createElement('span');label.textContent='Save to Projects';button.append(icon,label);button.onclick=()=>void open(true);
      const updateLanguage=()=>{label.textContent=translate('Save to Projects');label.dir=getLanguage()==='fa'?'rtl':'ltr';button.title=translate('Save to M Tools Projects');button.setAttribute('aria-label',button.title);};
      updateLanguage();window.addEventListener('mtools-language',updateLanguage);
      app.menu.settingsGroup.element.append(button);
    }
    const style = document.createElement('style');
    style.id = 'mtools-sidebar-style';
    style.textContent = `
      [data-testid="side-toolbar"] [data-testid="mtools-tab-button"] { order: 1; }
      .mtools-sidebar-icon { display:inline-block; width:22px; height:22px; background:currentColor;
        mask: url("${new URL('./MTool.svg', import.meta.url).href}") center/contain no-repeat; }
    `;
    document.getElementById(style.id)?.remove();
    document.head.append(style);
    if (!manager.getSidebarTabs().some(tab => tab.id === 'mtools')) {
      manager.registerSidebarTab({id:'mtools', title:'M Tools', tooltip:'Open M Tools', icon:'mtools-sidebar-icon', type:'custom', render:()=>{void open();}});
    }
    // This command belongs to our registered tab. Open the full manager directly,
    // without leaving an empty native sidebar behind the overlay.
    const command = manager.command.commands.find(c => c.id === 'Workspace.ToggleSidebarTab.mtools');
    if (command) command.function = open;
    if (new URLSearchParams(location.search).get('mtools') === '1') return open();
  },
  commands: [{id: 'MTools.Open', label: 'M Tools: Open library', function: open}],
  menuCommands: [{path: ['M Tools'], commands: ['MTools.Open']}],
});
