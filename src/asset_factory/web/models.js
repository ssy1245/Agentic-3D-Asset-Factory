// Model preview stays local; vendor-generated GLBs are fetched from our saved project files.
let modelSelection=null, modelViewerReady=null, modelPart="head";
const modelElement=id=>document.getElementById(id);
const characterExportSelection=new Map();
let projectExportSaving=false;
function sourceIsCurrent(op){
 const r=project?.revisions.find(r=>r.id===op.request?.source_revision);
 return r?.approved&&!r.stale&&project.current[op.stage]===r.id;
}
// Cache actual model renders; polling never repeats paid generation or keeps many GPU viewers alive.
const modelThumbnailCache=new Map();
function modelThumbnail(op){
 const preview=document.createElement('button');preview.type='button';preview.className='model-thumbnail';
 preview.setAttribute('aria-label',labels[op.stage]+' · 查看模型详情');
 const ready=op.status==='succeeded';
 preview.disabled=op.status!=='succeeded';preview.onclick=()=>openGeneratedModel(op);
 const hint=document.createElement('span');hint.className='thumbnail-hint';hint.textContent='点击查看模型详情';
 const placeholder=document.createElement('span');placeholder.className='thumbnail-placeholder';
 placeholder.textContent=ready?'正在加载模型缩略图…':op.status==='succeeded'?'模型已保存，网页预览暂不可用':'等待模型生成';
 preview.append(placeholder);
 if(!ready)return preview;
 const url=`/api/projects/${project.id}/geometry/${op.id}/preview`;
 const showImage=data=>{const img=document.createElement('img');img.src=data;img.alt=labels[op.stage]+' · 模型缩略图';preview.replaceChildren(img,hint);};
 if(modelThumbnailCache.has(url)){showImage(modelThumbnailCache.get(url));return preview;}
 ensureModelViewer().then(()=>{
  if(!preview.isConnected)return;
  const viewer=document.createElement('mesh-inspector');viewer.setAttribute('thumbnail','');viewer.setAttribute('model-format',op.model_format==='fbx'&&op.preview?.status!=='ready'?'fbx':'glb');viewer.setAttribute('camera-orbit','90deg 90deg auto');
  viewer.addEventListener('load',()=>{
   if(!preview.isConnected)return;
   try{const image=viewer.captureThumbnail();modelThumbnailCache.set(url,image);if(modelThumbnailCache.size>48)modelThumbnailCache.delete(modelThumbnailCache.keys().next().value);showImage(image);}catch(error){viewer.remove();placeholder.textContent='缩略图加载失败，点击查看详情';}
  },{once:true});
  viewer.addEventListener('error',()=>{viewer.remove();placeholder.textContent='缩略图加载失败，点击查看详情';},{once:true});
  preview.append(viewer);viewer.setMode(op.texture?'material':'clay');viewer.src=url;
 }).catch(()=>{placeholder.textContent='缩略图加载失败，点击查看详情';});
 return preview;
}
function renderCharacterExport(results){
 const root=modelElement('characterExportParts');root.replaceChildren();
 const ids={};
 for(const part of ['head','body','hair']){
  const options=results.filter(o=>o.stage===part&&o.status==='succeeded'&&sourceIsCurrent(o));
  const key=project.id+':'+part;
  const remembered=characterExportSelection.get(key);
  const selected=options.find(o=>o.id===remembered)||options.filter(o=>o.texture).at(-1)||options.at(-1);
  const label=document.createElement('label');label.append(document.createTextNode(labels[part]));
  const select=document.createElement('select');select.setAttribute('aria-label',labels[part]+' · 导出版本');
  if(!options.length){const option=document.createElement('option');option.textContent='等待模型生成';select.append(option);select.disabled=true;}
  for(const op of options){const option=document.createElement('option');option.value=op.id;option.textContent=(op.texture?'贴图模型':'白模')+' · '+op.id.slice(0,8);option.selected=op===selected;select.append(option);}
  if(selected)ids[part]=selected.id;
  select.onchange=()=>{characterExportSelection.set(key,select.value);renderCharacterExport(results);};
  label.append(select);root.append(label);
 }
 modelElement('characterExportName').textContent='项目文件名：'+project.name+'.zip';
 const ready=Object.keys(ids).length===3,link=modelElement('exportCharacter');
 link.classList.toggle('disabled',!ready);link.setAttribute('aria-disabled',String(!ready));
 link.href=ready?`/api/projects/${project.id}/project-package?${new URLSearchParams(ids)}`:'#';
}
async function saveBlend(event,link,name,packageExport=false){
 event.preventDefault();
 if(link.getAttribute('aria-disabled')==='true'||projectExportSaving)return;
 const url=link.href;
 const extension=packageExport?'.zip':'.blend';
 projectExportSaving=true;link.setAttribute('aria-busy','true');
 let writable;
 try{
  let file;
  if(typeof window.showSaveFilePicker==='function')file=await window.showSaveFilePicker({suggestedName:name+extension,types:[packageExport?{description:'Project package',accept:{'application/zip':['.zip']}}:{description:'Blender scene',accept:{'application/octet-stream':['.blend']}}]});
  say('正在导出 Blender 文件，请稍候…');
  const response=await fetch(url);
  if(!response.ok){const error=await response.json().catch(()=>({}));throw new Error(error.detail||'导出失败，请重试。');}
  const blob=await response.blob();
  if(file){writable=await file.createWritable();await writable.write(blob);await writable.close();writable=null;}
  else{const download=document.createElement('a');const objectURL=URL.createObjectURL(blob);download.href=objectURL;download.download=name+extension;download.click();setTimeout(()=>URL.revokeObjectURL(objectURL),60000);}
  say('Blender 文件已导出。');
 }catch(error){
  if(writable)await writable.abort().catch(()=>{});
  if(error.name!=='AbortError')say(error.message);
 }finally{projectExportSaving=false;link.removeAttribute('aria-busy');}
}
function blendName(){return project.name.replace(/[<>:"/\\|?*\x00-\x1f]/g,'_').replace(/^[ .]+|[ .]+$/g,'').slice(0,100)||'project';}
modelElement('exportCharacter').onclick=event=>saveBlend(event,modelElement('exportCharacter'),blendName(),true);
function renderModelLibrary(){
 const visible=!!project&&stage==='models';
 modelElement('modelLibrary').hidden=!visible;
 const root=modelElement('modelCandidates');root.replaceChildren();
 updateModelActions();
 if(!visible)return;
 const results=project.operations.filter(o=>o.kind==='geometry');
 renderCharacterExport(results);
 modelElement('modelEngine').textContent=config?.tripo_model==='P2-20260801'?'Engine: Tripo P2.0 · P2-20260801':`Engine: Tripo ${config?.tripo_model||'—'}`;
 const tabs=modelElement('modelPartTabs');tabs.replaceChildren();
 for(const part of ['head','body','hair']){const button=document.createElement('button');button.className='secondary';button.textContent=labels[part];button.setAttribute('aria-current',String(modelPart===part));button.onclick=()=>{modelPart=part;render();};tabs.append(button);}
 modelElement('modelPartTitle').textContent=labels[modelPart]+' · 3D 模型候选';
 modelElement('modelPartHint').textContent='每个部件单独检查与确认；本页只展示该部件的候选版本。';
 const matching=results.filter(o=>!o.texture&&sourceIsCurrent(o)&&o.model===config?.tripo_model&&o.quad===true&&o.input_mode==='multiview_to_model'&&o.face_limit===(o.stage==='head'?5000:20000));
 const pending=project.operations.some(o=>['queued','running','unknown'].includes(o.status));
 const complete=['head','body','hair'].filter(part=>matching.some(o=>o.stage===part&&o.status==='succeeded')).length;
 const submitted=['head','body','hair'].every(part=>matching.some(o=>o.stage===part));
 modelElement('generateModels').disabled=!!project.geometry_paused||busy||!config?.tripo_configured||!stepUnlocked('models')||pending||submitted;
 modelElement('generateModels').textContent=submitted?'三个模型已提交':'开始并行生成三个模型';
 modelElement('modelBatchStatus').textContent=!config?.tripo_configured?'请配置 Tripo API 后开始模型生成。':`3D 完成进度：${complete} / 3`;
 if(project.geometry_paused)modelElement('modelBatchStatus').textContent='3D 生成已暂停，正在核对 P2.0 接口。';
 modelElement('modelLibraryEmpty').hidden=results.some(o=>o.stage===modelPart);
 for(const [index,op] of results.filter(o=>o.stage===modelPart).entries()){
  const card=document.createElement('article');card.className='model-candidate';
  const name=document.createElement('h3');name.textContent=labels[op.stage]+' · '+(index+1)+(op.texture?' · Texture':'');
  const status=document.createElement('p');status.className='muted small';
  const states={queued:'等待执行',running:'生成中',unknown:'结果待核对',failed:'失败'};
  status.textContent=op.status==='succeeded'?(!sourceIsCurrent(op)?'模型参考已变更，请重新检查当前版本':op.visual_approved?'模型已确认':'等待模型检查'):states[op.status]||op.status;
  const button=document.createElement('button');button.className='secondary';button.textContent='查看 3D 模型';button.disabled=op.status!=='succeeded';button.onclick=()=>openGeneratedModel(op);
  const progress=document.createElement('progress');progress.max=100;progress.value=op.progress||0;progress.hidden=!['queued','running'].includes(op.status);
  const note=document.createElement('p');note.className='model-spec';note.textContent=op.status==='running'?`${op.progress||0}%`:op.quad?`FBX · ${op.face_limit.toLocaleString()} faces · Quad`:'旧设置模型 · GLB 三角网格';
  if(['queued','running'].includes(op.status)){const spinner=document.createElement('span');spinner.className='spinner';spinner.setAttribute('aria-hidden','true');status.prepend(spinner);}
  const input=document.createElement('p');input.className='model-input muted small';input.textContent=op.texture?'贴图目标：4K · detailed · 实际分辨率待核对':op.input_mode==='multiview_to_model'?'四视图输入 · Front / Left / Back / Right':'输入：单张正面图（旧流程）';
  const actions=document.createElement('div');actions.className='model-card-actions';actions.append(button);
  card.append(modelThumbnail(op),name,status,progress,note,input,actions);
  if(op.status==='unknown'&&op.provider_task_id){const check=document.createElement('button');check.className='ghost';check.textContent='查询原任务';check.onclick=async()=>{try{await api(`/api/projects/${project.id}/geometry/${op.id}/refresh`,{method:'POST'});await refresh();}catch(error){say(error.message);}};card.append(check);}
  if(op.model_format==='fbx'&&op.status==='succeeded'){const download=document.createElement('a');download.className='secondary model-download';download.textContent='下载原始 FBX';download.href=op.download_url;actions.append(download);}

  if(op.error){const error=document.createElement('p');error.className='error';error.textContent=op.error;card.append(error);}
  root.append(card);
 }
}
modelElement('generateModels').onclick=async()=>{
 if(busy||!stepUnlocked('models'))return;
 busy=true;render();
 try{
  const batch=await api(`/api/projects/${project.id}/generate-models`,jsonOptions({component_revisions:Object.fromEntries(['head','body','hair'].map(part=>[part,project.current[part]]))}));
  const errors=batch.results.filter(v=>v.error);
  say(errors.length?errors.map(v=>labels[v.stage]+': '+v.error).join('\n'):'已并行提交三个 3D 模型任务。');await refresh();
 }catch(error){say(error.message);}finally{busy=false;render();}
};
async function ensureModelViewer(){
 if(!modelViewerReady)modelViewerReady=import('/static/mesh-viewer.js?v=texture-preview-1').then(()=>customElements.whenDefined('mesh-inspector')).catch(error=>{modelViewerReady=null;throw error;});
 return modelViewerReady;
}
function updateModelActions(){
 const s=modelSelection;if(!s)return;
 const op=s.oid&&project?.id===s.pid?project.operations.find(o=>o.id===s.oid):null;
 const valid=op&&sourceIsCurrent(op);
 modelElement('approveModel').hidden=!op;
 const child=op&&!op.texture?project.operations.find(o=>o.parent_model_id===op.id):null;
 modelElement('approveModel').disabled=!s.loaded||!valid||!!(op?.texture&&op?.visual_approved)||!!child||busy;
 modelElement('approveModel').textContent=op?.texture?(op.visual_approved?'最终确认完成':'最终确认贴图模型'):child?'贴图已提交':'生成贴图';
 modelElement('regenerateModel').hidden=!op||!!op.texture;
 modelElement('regenerateModel').disabled=!valid||busy||project.operations.some(o=>['queued','running','unknown'].includes(o.status)&&(o.status==='unknown'||o.kind!=='geometry'||(o.stage===op?.stage&&!o.texture)));
 modelElement('viewTextureResult').hidden=child?.status!=='succeeded';
 if(child){
  modelElement('modelStatus').textContent=child.status==='succeeded'?'贴图生成完成，请查看结果并最终确认。':['queued','running'].includes(child.status)?`贴图生成中… ${child.progress||0}%`:child.status==='unknown'?'贴图任务状态待核对，请查询原任务。':child.error||'贴图生成失败，请核对原任务。';
 }
 modelElement('saveModel').textContent=op?.texture?'下载贴图模型':op?.model_format==='fbx'?'下载原始四边形 FBX':'下载 GLB 到本地';
 const exportable=valid&&op.status==='succeeded';
 for(const [id,suffix] of [['saveModel','download'],['exportBlender','blend']]){
  const link=modelElement(id);link.classList.toggle('disabled',!exportable);link.setAttribute('aria-disabled',String(!exportable));link.href=exportable?`/api/projects/${s.pid}/geometry/${s.oid}/${suffix}`:'#';
 }
 modelElement('modelExportNote').textContent=op?'直接下载 Blender 文件（.blend），包含模型与贴图。贴图生成是可选步骤。':'当前仅预览本地文件，未上传或保存到角色项目。';
}
async function showModel(selection,src,title){
 closeModelPreview();modelSelection=selection;
 modelElement('modelTitle').textContent=title;modelElement('modelInfo').textContent='';modelElement('modelStatus').textContent='正在加载 3D 模型…';
 modelElement('modelViewer').hidden=!src;modelElement('modelDisplayModes').hidden=!src;modelElement('modelCameraButtons').hidden=!src;
 modelElement('modelDialog').showModal();updateModelActions();
 try{
  if(!src){modelElement('modelStatus').textContent='请先下载原始 FBX 在 Blender 检查，再确认模型。';return;}
  await ensureModelViewer();if(modelSelection!==selection)return;
  const viewer=modelElement('modelViewer');viewer.setAttribute('camera-orbit','90deg 90deg auto');viewer.setWireEnabled(false);viewer.setDoubleSided(true);modelElement('modelDoubleSided').checked=true;modelElement('modelTopologyToggle').checked=false;const textured=project?.operations.find(o=>o.id===selection.oid)?.texture;viewer.setMode(textured?'material':'clay');for(const button of document.querySelectorAll('[data-model-mode]'))button.setAttribute('aria-pressed',String(button.dataset.modelMode===(textured?'material':'clay')));viewer.setAttribute('model-format',selection.format||'glb');viewer.src=src;
 }catch(error){if(modelSelection===selection)modelElement('modelStatus').textContent='模型预览组件未就绪，请安装网页依赖或检查服务。';}
}
async function openGeneratedModel(op){
 const externalCheck=false;
 const selection={pid:project.id,oid:op.id,loaded:false,externalCheck,format:op.model_format==='fbx'&&op.preview?.status!=='ready'?'fbx':'glb'};
 await showModel(selection,externalCheck?null:`/api/projects/${project.id}/geometry/${op.id}/preview`,labels[op.stage]+' · 3D 模型预览');
 try{const info=await api(`/api/projects/${selection.pid}/geometry/${selection.oid}/info`);if(modelSelection===selection)modelElement('modelInfo').textContent=info.format==='FBX'?`FBX · ${(info.bytes/1024/1024).toFixed(2)} MB · target ${info.requested_face_limit} faces${info.faces!==undefined?` · actual ${info.faces} faces / ${info.quad_faces} quads`:' · actual topology not measured'} · ${selection.format==='fbx'?'Direct FBX browser preview':'Derived GLB preview'}; original FBX preserved`:`GLB · ${(info.bytes/1024/1024).toFixed(2)} MB · ${info.meshes} meshes · ${info.materials} materials`;}catch(error){if(modelSelection===selection)modelElement('modelInfo').textContent=error.message;}
}
function closeModelPreview(){
 const viewer=modelElement('modelViewer');viewer.removeAttribute('src');
 if(modelSelection?.localURL)URL.revokeObjectURL(modelSelection.localURL);
 modelSelection=null;if(modelElement('modelDialog').open)modelElement('modelDialog').close();
}
modelElement('closeModel').onclick=closeModelPreview;
modelElement('modelDialog').addEventListener('cancel',event=>{event.preventDefault();closeModelPreview();});
modelElement('modelViewer').addEventListener('load',()=>{if(!modelSelection)return;modelSelection.loaded=true;modelElement('modelStatus').textContent='模型已加载，可以旋转检查。';updateModelActions();});
modelElement('modelViewer').addEventListener('error',()=>{if(!modelSelection)return;modelSelection.loaded=false;modelElement('modelStatus').textContent='模型加载失败，请检查文件或重新下载原任务结果。';updateModelActions();});
for(const button of document.querySelectorAll('[data-model-orbit]'))button.onclick=()=>{modelElement('modelViewer').setAttribute('camera-orbit',button.dataset.modelOrbit);modelElement('modelViewer').jumpCameraToGoal?.();};
modelElement('resetModelCamera').onclick=()=>{modelElement('modelViewer').setAttribute('camera-orbit','90deg 90deg auto');modelElement('modelViewer').setAttribute('camera-target','auto auto auto');modelElement('modelViewer').setAttribute('field-of-view','auto');modelElement('modelViewer').jumpCameraToGoal?.();};
modelElement('saveModel').onclick=event=>{if(modelElement('saveModel').getAttribute('aria-disabled')==='true')event.preventDefault();};
modelElement('exportBlender').onclick=event=>{const op=project?.operations.find(o=>o.id===modelSelection?.oid);if(!op){event.preventDefault();return;}return saveBlend(event,modelElement('exportBlender'),blendName()+'_'+op.stage);};
modelElement('approveModel').onclick=async()=>{
 const s=modelSelection;if(!s?.loaded||!s.oid||busy)return;
 const op=project.operations.find(o=>o.id===s.oid);
 if(!op||!sourceIsCurrent(op)||(op.texture&&op.visual_approved))return;
 busy=true;updateModelActions();
 modelElement('modelStatus').textContent=op.texture?'正在确认贴图模型…':'正在提交贴图生成任务…';
 try{
  await api(`/api/projects/${s.pid}/geometry/${s.oid}/${op.texture?'approve':'texture'}`,jsonOptions({checked:true}));
  await refresh();
  if(modelSelection===s&&op.texture)modelElement('modelStatus').textContent='贴图模型已最终确认，可下载或导出。';
 }catch(error){if(modelSelection===s)modelElement('modelStatus').textContent=error.message;}
 finally{busy=false;updateModelActions();}
};
modelElement('viewTextureResult').onclick=()=>{
 const child=project.operations.find(o=>o.parent_model_id===modelSelection?.oid&&o.status==='succeeded');
 if(child)openGeneratedModel(child);
};
modelElement('regenerateModel').onclick=async()=>{
 const s=modelSelection;const op=project.operations.find(o=>o.id===s?.oid);if(!op||op.texture||op.texture_committed||busy)return;
 const key='pending-model-regeneration-'+op.id;
 let payload=JSON.parse(localStorage.getItem(key)||'null');
 if(!payload){payload={stage:op.stage,source_revision:op.request.source_revision,regenerate_model_id:op.id,request_id:crypto.randomUUID()};localStorage.setItem(key,JSON.stringify(payload));}
 busy=true;updateModelActions();
 try{await api(`/api/projects/${s.pid}/geometry`,jsonOptions(payload));localStorage.removeItem(key);closeModelPreview();await refresh();say('已提交新的白模候选，原模型保留。');}
 catch(error){if(error.httpStatus)localStorage.removeItem(key);if(modelSelection===s)modelElement('modelStatus').textContent=error.message;}
 finally{busy=false;render();}
};
modelElement('localModelFile').onchange=async event=>{
 const input=event.target,file=input.files[0];input.value='';if(!file)return;
 if(!/\.glb$/i.test(file.name)||file.size>100*1024*1024){say('请选择不超过 100 MB 的 GLB 文件。');return;}
 const bytes=new Uint8Array(await file.slice(0,12).arrayBuffer());
 if(bytes.length!==12||String.fromCharCode(...bytes.slice(0,4))!=='glTF'){say('模型文件不是有效的 GLB');return;}
 const url=URL.createObjectURL(file);await showModel({localURL:url,loaded:false},url,'本地 GLB 预览');
};

for(const button of document.querySelectorAll('[data-model-mode]'))button.onclick=()=>{modelElement('modelViewer').setMode?.(button.dataset.modelMode);for(const item of document.querySelectorAll('[data-model-mode]'))item.setAttribute('aria-pressed',String(item===button));};

modelElement('modelTopologyToggle').onchange=event=>modelElement('modelViewer').setWireEnabled?.(event.target.checked);

modelElement('modelDoubleSided').onchange=event=>modelElement('modelViewer').setDoubleSided(event.target.checked);
