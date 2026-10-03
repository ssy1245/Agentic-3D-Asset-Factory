// Model preview stays local; vendor-generated GLBs are fetched from our saved project files.
let modelSelection=null, modelViewerReady=null, modelPart="head";
const modelElement=id=>document.getElementById(id);
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
  preview.append(viewer);viewer.src=url;
 }).catch(()=>{placeholder.textContent='缩略图加载失败，点击查看详情';});
 return preview;
}
function renderModelLibrary(){
 const visible=!!project&&stage==='models';
 modelElement('modelLibrary').hidden=!visible;
 const root=modelElement('modelCandidates');root.replaceChildren();
 if(!visible)return;
 const results=project.operations.filter(o=>o.kind==='geometry');
 const tabs=modelElement('modelPartTabs');tabs.replaceChildren();
 for(const part of ['head','body','hair']){const button=document.createElement('button');button.className='secondary';button.textContent=labels[part];button.setAttribute('aria-current',String(modelPart===part));button.onclick=()=>{modelPart=part;render();};tabs.append(button);}
 modelElement('modelPartTitle').textContent=labels[modelPart]+' · 3D 模型候选';
 modelElement('modelPartHint').textContent='每个部件单独检查与确认；本页只展示该部件的候选版本。';
 const matching=results.filter(o=>sourceIsCurrent(o)&&o.quad===true&&o.input_mode==='multiview_to_model'&&o.face_limit===(o.stage==='head'?5000:20000));
 const pending=project.operations.some(o=>['queued','running','unknown'].includes(o.status));
 const complete=['head','body','hair'].filter(part=>matching.some(o=>o.stage===part&&o.status==='succeeded')).length;
 const submitted=['head','body','hair'].every(part=>matching.some(o=>o.stage===part));
 modelElement('generateModels').disabled=busy||!config?.tripo_configured||!stepUnlocked('models')||pending||submitted;
 modelElement('generateModels').textContent=submitted?'三个模型已提交':'开始并行生成三个模型';
 modelElement('modelBatchStatus').textContent=!config?.tripo_configured?'请配置 Tripo API 后开始模型生成。':`3D 完成进度：${complete} / 3`;
 modelElement('modelLibraryEmpty').hidden=results.some(o=>o.stage===modelPart);
 for(const [index,op] of results.filter(o=>o.stage===modelPart).entries()){
  const card=document.createElement('article');card.className='model-candidate';
  const name=document.createElement('h3');name.textContent=labels[op.stage]+' · '+(index+1);
  const status=document.createElement('p');status.className='muted small';
  const states={queued:'等待执行',running:'生成中',unknown:'结果待核对',failed:'失败'};
  status.textContent=op.status==='succeeded'?(!sourceIsCurrent(op)?'模型参考已变更，请重新检查当前版本':op.visual_approved?'模型已确认':'等待模型检查'):states[op.status]||op.status;
  const button=document.createElement('button');button.className='secondary';button.textContent='查看 3D 模型';button.disabled=op.status!=='succeeded';button.onclick=()=>openGeneratedModel(op);
  const progress=document.createElement('progress');progress.max=100;progress.value=op.progress||0;progress.hidden=!['queued','running'].includes(op.status);
  const note=document.createElement('p');note.className='model-spec';note.textContent=op.status==='running'?`${op.progress||0}%`:op.quad?`FBX · ${op.face_limit.toLocaleString()} faces · Quad`:'旧设置模型 · GLB 三角网格';
  if(['queued','running'].includes(op.status)){const spinner=document.createElement('span');spinner.className='spinner';spinner.setAttribute('aria-hidden','true');status.prepend(spinner);}
  const input=document.createElement('p');input.className='model-input muted small';input.textContent=op.input_mode==='multiview_to_model'?'四视图输入 · Front / Left / Back / Right':'输入：单张正面图（旧流程）';
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
 if(!modelViewerReady)modelViewerReady=import('/static/mesh-viewer.js').then(()=>customElements.whenDefined('mesh-inspector')).catch(error=>{modelViewerReady=null;throw error;});
 return modelViewerReady;
}
function updateModelActions(){
 const s=modelSelection;if(!s)return;
 const op=s.oid&&project?.id===s.pid?project.operations.find(o=>o.id===s.oid):null;
 const valid=op&&sourceIsCurrent(op);
 modelElement('approveModel').hidden=!op;
 modelElement('approveModel').disabled=!(s.loaded||s.externalCheck)||!valid||!!op?.visual_approved||busy;
 modelElement('approveModel').textContent=s.externalCheck?'已在 Blender 检查，确认模型':'检查完成，确认此模型';
 modelElement('saveModel').textContent=op?.model_format==='fbx'?'下载原始四边形 FBX':'下载 GLB 到本地';
 const approved=valid&&op.visual_approved;
 for(const [id,suffix] of [['saveModel','download'],['exportBlender','blender-package']]){
  const link=modelElement(id);link.classList.toggle('disabled',!approved);link.setAttribute('aria-disabled',String(!approved));link.href=approved?`/api/projects/${s.pid}/geometry/${s.oid}/${suffix}`:'#';
 }
 modelElement('modelExportNote').textContent=op?'确认后可导出。Blender 文件包包含模型和导入脚本，不会自动拼接或绑定。':'当前仅预览本地文件，未上传或保存到角色项目。';
}
async function showModel(selection,src,title){
 closeModelPreview();modelSelection=selection;
 modelElement('modelTitle').textContent=title;modelElement('modelInfo').textContent='';modelElement('modelStatus').textContent='正在加载 3D 模型…';
 modelElement('modelViewer').hidden=!src;modelElement('modelDisplayModes').hidden=!src;modelElement('modelCameraButtons').hidden=!src;
 modelElement('modelDialog').showModal();updateModelActions();
 try{
  if(!src){modelElement('modelStatus').textContent='请先下载原始 FBX 在 Blender 检查，再确认模型。';return;}
  await ensureModelViewer();if(modelSelection!==selection)return;
  const viewer=modelElement('modelViewer');viewer.setAttribute('camera-orbit','90deg 90deg auto');viewer.setWireEnabled(false);modelElement('modelTopologyToggle').checked=false;viewer.setMode('clay');for(const button of document.querySelectorAll('[data-model-mode]'))button.setAttribute('aria-pressed',String(button.dataset.modelMode==='clay'));viewer.setAttribute('model-format',selection.format||'glb');viewer.src=src;
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
for(const id of ['saveModel','exportBlender'])modelElement(id).onclick=event=>{if(modelElement(id).getAttribute('aria-disabled')==='true')event.preventDefault();};
modelElement('approveModel').onclick=async()=>{
 const s=modelSelection;if(!(s?.loaded||s?.externalCheck)||!s.oid||busy)return;
 modelElement('approveModel').disabled=true;
 try{await api(`/api/projects/${s.pid}/geometry/${s.oid}/approve`,jsonOptions({checked:true}));await refresh();if(modelSelection===s){updateModelActions();modelElement('modelStatus').textContent='模型已确认，可下载或导出。';}}catch(error){modelElement('modelStatus').textContent=error.message;updateModelActions();}
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
