const $ = id => document.getElementById(id);
const labels = {design:'整体设计',turnaround:'四视图',head:'头部',body:'身体与服装',hair:'头发',models:'3D 生成'};
const descriptions = {design:'确定角色的轮廓、配色和服装。',turnaround:'让正面、侧面和背面的设计保持一致。',head:'准备不含头发的头部参考，保留脸部身份。',body:'分清服装、皮肤与装饰，让轮廓可读。',hair:'独立展示发型结构、发束和饰品。',models:'三个部件并行生成，完成后检查并导出模型。'};
let tripoWallet=null, promptTemplates={}, sheetOpen=false, busySince=null, renderedStage=null;
let brushStrokes=[], annotationTool='brush', currentStroke=null;
let project=null, stage='design', selected=null, region=null, drawing=null, busy=false, config=null, designMode='text', baseImageId=null, feedbackImages=[];
let approvalActionKey=null, approvalSettled=false, approvalTransitionTimer=null;
function renderApprovalAction(r,active,operations){
 const button=$('approve'),key=`${project?.id}:${r?.id}:${!!r?.approved}`;
 if(approvalActionKey!==key){
  clearTimeout(approvalTransitionTimer);approvalActionKey=key;
  approvalSettled=!r?.approved||matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(r?.approved&&!approvalSettled){
   approvalTransitionTimer=setTimeout(()=>{if(approvalActionKey!==key)return;approvalSettled=true;if(stage!=='models')render();},850);
  }
 }
 const reopen=!!r?.approved&&approvalSettled;
 button.classList.toggle('reopen-action',reopen);
 button.classList.toggle('approval-confirmed',!!r?.approved&&!approvalSettled);
 button.textContent=r?.approved?(reopen?'取消确认，继续修改':'已确认'):stage==='design'?'确认并生成四视图':stage==='turnaround'?'确认并生成三个部件':'确认此部件';
 button.disabled=!r||r.stale||busy||r.id!==project?.current[stage]||r.quality_review?.status==='running'||(r.approved? !approvalSettled||operations.some(o=>['queued','running','unknown'].includes(o.status)):!!active||stage!=='design'&&r.view_split?.status!=='ready');
 button.dataset.action=reopen?'reopen':'approve';
}
async function api(path, options={}) {
  const response=await fetch(path,options);
  if(!response.ok){const error=await response.json().catch(()=>({}));const failure=new Error(typeof error.detail==='string'?error.detail:'输入不完整或请求失败，请检查填写内容。');failure.httpStatus=response.status;throw failure;}
  return response.json();
}
const jsonOptions = body => ({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
function say(message){$('notice').textContent=message;}
function pendingRequest(){try{return JSON.parse(localStorage.getItem('pending-generation-'+project?.id)||'null');}catch{return null;}}
function current(){return project?.revisions.find(r=>r.id===project.current[stage]);}
function shown(){return project?.revisions.find(r=>r.id===selected)||current();}
function resetRegion(){region=null; drawing=null;brushStrokes=[];currentStroke=null;drawSelection();}
async function loadProjects(){const list=await api('/api/projects');$('projects').replaceChildren();for(const p of list){const o=new Option(p.name,p.id);$('projects').add(o);}if(project)$('projects').value=project.id;return list;}
async function loadProject(id){project=await api(`/api/projects/${id}`);$('projects').value=project.id;localStorage.setItem('reference-project',id);if(stepUnlocked('models'))stage='models';selected=project.current[stage]||null;feedbackImages=[];baseImageId=project.current.design?null:[...(project.reference_images||[])].reverse().find(a=>a.purpose==='base')?.id||null;designMode=project.current.design||baseImageId?'image':'text';resetRegion();render();}
function stepUnlocked(s){const order=Object.keys(labels);const parents=['head','body','hair'].includes(s)?['design','turnaround']:order.slice(0,order.indexOf(s));return !!project&&parents.every(parent=>{const r=project.revisions.find(v=>v.id===project.current[parent]);return r?.approved&&!r.stale;});}
// Sidebar states follow each branch independently; a busy sibling never locks a part.
function workflowState(s){
  if(!stepUnlocked(s))return {text:'尚未解锁',tone:'locked'};
  if(s==='models'){
    const ops=project.operations.filter(o=>o.kind==='geometry'&&sourceIsCurrent(o));
    if(ops.some(o=>o.status==='unknown'))return {text:'结果待核对',tone:'attention'};
    if(ops.some(o=>['queued','running'].includes(o.status)))return {text:'生成中',tone:'working'};
    if(ops.some(o=>o.status==='failed'))return {text:'失败',tone:'attention'};
    if(['head','body','hair'].every(part=>ops.some(o=>o.stage===part&&o.visual_approved)))return {text:'已确认',tone:'done'};
    return {text:ops.length?'等待模型检查':'等待模型生成',tone:'ready'};
  }
  const r=project.revisions.find(v=>v.id===project.current[s]);
  const op=[...project.operations].reverse().find(o=>o.stage===s&&o.kind!=='geometry');
  if(op?.status==='unknown')return {text:'结果待核对',tone:'attention'};
  if(op?.status==='queued')return {text:'等待执行',tone:'working'};
  if(op?.status==='running')return {text:'生成中',tone:'working'};
  if(r?.stale)return {text:'上游已变更',tone:'attention'};
  if(op?.status==='failed')return {text:'失败',tone:'attention'};
  if(r?.quality_review?.status==='running')return {text:'AI 检查中',tone:'working'};
  if(r?.approved)return {text:'已确认',tone:'done'};
  if(r?.quality_review?.status==='completed'&&r.quality_review.verdict!=='pass')return {text:'需要人工检查',tone:'attention'};
  if(r?.quality_review?.status==='unavailable')return {text:'AI 检查不可用，请人工检查',tone:'attention'};
  if(r&&s!=='design'&&r.view_split?.status!=='ready')return {text:'视图待拆分检查',tone:'attention'};
  return {text:r?'等待确认':'等待参考',tone:'ready'};
}
function workflowButton(s,marker,component=false){
  const state=workflowState(s),button=document.createElement('button');
  button.disabled=busy||!stepUnlocked(s);
  button.className='step workflow-step'+(component?' component-step':'')+(stage===s?' active':'');
  button.dataset.state=state.tone;
  button.setAttribute('aria-current',stage===s?'step':'false');
  button.title=!stepUnlocked(s)?component?'确认整体四视图后，三个部件同时解锁':'请按顺序确认前面的步骤':'';
  const icon=document.createElement('span');icon.className='num';
  icon.textContent=state.tone==='done'?'✓':marker;
  if(state.tone==='working')icon.classList.add('workflow-spinner');
  const text=document.createElement('div');text.className='workflow-label';text.textContent=labels[s];
  const sub=document.createElement('div');sub.className='subtitle';sub.textContent=state.text;
  text.append(sub);button.append(icon,text);
  button.onclick=()=>{if(busy||!stepUnlocked(s))return;stage=s;selected=project.current[s]||null;resetRegion();feedbackImages=[];$('feedback').value='';say('');render();};
  return button;
}
function renderWorkflow(){
  const nav=$('steps');nav.replaceChildren();
  nav.append(workflowButton('design','01'),workflowButton('turnaround','02'));
  const group=document.createElement('section');group.className='parallel-group';
  group.setAttribute('aria-label','并行部件');
  const title=document.createElement('div');title.className='parallel-heading';
  const number=document.createElement('span');number.className='parallel-phase';number.textContent='03';
  const label=document.createElement('strong');label.textContent='并行部件';
  title.append(number,label);
  const note=document.createElement('p');note.className='parallel-note';note.textContent='同时生成 · 各自检查与确认';
  const branches=document.createElement('div');branches.className='parallel-branches';
  for(const s of ['head','body','hair'])branches.append(workflowButton(s,'•',true));
  const count=['head','body','hair'].filter(s=>{const r=project?.revisions.find(v=>v.id===project.current[s]);return stepUnlocked(s)&&r?.approved&&!r.stale;}).length;
  const footer=document.createElement('div');footer.className='parallel-progress';
  const progress=document.createElement('span');progress.textContent=`${count} / 3`;
  const caption=document.createElement('span');caption.textContent='部件已确认';footer.append(progress,caption);
  group.append(title,note,branches,footer);nav.append(group,workflowButton('models','04'));
  if(stepUnlocked('models')){
    const parts=document.createElement('div');parts.className='model-sidebar-parts';
    for(const part of ['head','body','hair']){const button=document.createElement('button');button.className='ghost';button.textContent=labels[part]+' · 3D';button.disabled=busy;button.setAttribute('aria-current',String(stage==='models'&&modelPart===part));button.onclick=()=>{if(busy)return;stage='models';modelPart=part;render();};parts.append(button);}nav.append(parts);
  }

}
function render(){
  if(project&&!stepUnlocked(stage)){stage=Object.keys(labels).find(s=>stepUnlocked(s)&&!project.revisions.find(r=>r.id===project.current[s])?.approved)||'design';selected=project.current[stage]||null;resetRegion();feedbackImages=[];}
  const stageChanged=renderedStage!==stage;renderedStage=stage;
  $('promptPreview').textContent=promptTemplates[stage]?promptTemplates[stage].common+'\n\n'+promptTemplates[stage].instructions:'读取本步骤规则中…';
  $('serviceStatus').textContent=`图片 API：${config?.providers.includes('openai')?'已配置':'未配置'}\n3D API：${config?.tripo_configured?'已配置':'未配置'}`;$('serviceStatus').style.whiteSpace='pre-line';
  $('projects').disabled=busy;$('newProject').disabled=busy;
  $('projectName').textContent=project?.name||'开始一个新角色';
  $('stageTitle').textContent=labels[stage];$('stageDesc').textContent=descriptions[stage];
  $('stageEyebrow').textContent=stage==='models'?'阶段 04 / 04':['head','body','hair'].includes(stage)?'阶段 03 / 04 · 并行部件':stage==='design'?'阶段 01 / 04':'阶段 02 / 04';
  renderWorkflow();
  $('imageWorkspace').hidden=stage==='models';
  renderModelLibrary();
  $('export').classList.toggle('disabled',!project);$('export').href=project?`/api/projects/${project.id}/export`:'#';
  if(stage==='models'){$('componentsPanel').hidden=true;if(stageChanged)window.scrollTo(0,0);return;}
  $('designControls').hidden=stage!=='design';$('baseControls').hidden=designMode!=='image';$('feedbackReferences').hidden=stage==='design'&&designMode==='text';
  $('textMode').classList.toggle('active',designMode==='text');$('imageMode').classList.toggle('active',designMode==='image');
  $('designModeHelp').textContent=designMode==='text'?'根据角色设计和文字要求生成新的整体设计，不使用当前图片。':'使用上传的初始图片或当前版本，再结合文字和修改参考图片生成。';
  $('useCurrent').hidden=!project?.current.design||!baseImageId;
  showReferences('basePreview',(project?.reference_images||[]).filter(a=>a.id===baseImageId));
  showReferences('feedbackPreviews',feedbackImages,true);
  const r=shown();renderViews(r);$('empty').hidden=!!r;$('imageWrap').hidden=!r;
  if(r){if($('referenceImage').dataset.id!==r.id){$('referenceImage').dataset.id=r.id;$('referenceImage').src=r.image_url;resetRegion();}
    const versions=project.revisions.filter(v=>v.stage===stage);$('imageLabel').textContent=`${labels[stage]} · V${versions.findIndex(v=>v.id===r.id)+1}`;
    $('approvalBadge').textContent=r.stale?'需更新':r.approved?'已确认':r.id!==project.current[stage]?'历史版本':'待确认';$('approvalBadge').className='pill'+(r.approved?' approved':'');
  }else{$('imageLabel').textContent='等待第一张参考图';$('approvalBadge').textContent='待生成';$('approvalBadge').className='pill';}
  const operations=project?.operations||[];const active=operations.find(o=>o.stage===stage&&['queued','running','unknown'].includes(o.status))||operations.find(o=>o.status==='unknown');
  $('brushTool').classList.toggle('active',annotationTool==='brush');$('boxTool').classList.toggle('active',annotationTool==='box');$('undoStroke').disabled=!brushStrokes.length||busy||!!active;
  $('generate').disabled=!project||busy||!!active||r?.quality_review?.status==='running'||!!r&&r.id!==project.current[stage];
  $('generate').textContent=pendingRequest()?'核对并重发原提交':stage==='design'&&designMode==='text'?'根据文字生成整体设计':stage==='design'&&baseImageId?'根据初始图片生成':r?.stale?'根据新设计重新生成':r?'根据意见生成新版本':'生成参考图';
  renderApprovalAction(r,active,operations);
  $('upload').disabled=!project||busy||!!active;$('baseUpload').disabled=!project||busy||!!active;$('feedbackUpload').disabled=!project||busy||!!active;$('textMode').disabled=busy||!!active;$('imageMode').disabled=busy||!!active;
  $('feedbackDropZone').setAttribute('aria-disabled',String($('feedbackUpload').disabled));$('feedbackDropZone').tabIndex=$('feedbackUpload').disabled?-1:0;
  if($('feedbackUpload').disabled)clearFeedbackDrag();
  const reviewing=r?.quality_review?.status==='running';
  const waiting=busy||reviewing||!!active&&active.status!=='unknown';
  if(busy&&!busySince)busySince=Date.now();if(!busy)busySince=null;
  $('waitingOverlay').hidden=!waiting;$('viewerPanel').setAttribute('aria-busy',String(waiting));
  $('waitingTitle').textContent=reviewing?'AI 正在检查部件…':active?.status==='running'?'正在生成图片…':active?.status==='queued'?'请求已提交，等待生成…':'正在处理请求…';
  $('waitingDetail').textContent=reviewing?'正在检查结构分离、残留和颈部衔接，请稍候。':active?'模型正在处理，结果返回后会自动更新。请勿重复提交。':'正在提交或保存，请稍候。';
  const since=active?.started_at||active?.created_at;
  const elapsed=Math.max(0,Math.floor((Date.now()-(since?Date.parse(since):busySince||Date.now()))/1000));
  $('waitingElapsed').textContent=waiting?`已等待 ${elapsed} 秒`:'';
  $('progress').hidden=true;
  $('operationError').replaceChildren();$('operationError').hidden=true;
  const problem=active?.status==='unknown'?active:[...operations].reverse().find(o=>o.stage===stage&&o.status==='failed');
  if(problem){$('operationError').hidden=false;const p=document.createElement('p');p.textContent=problem.error;$('operationError').append(p);
    if(problem.status==='unknown'){const button=document.createElement('button');button.className='secondary full';button.textContent='已核对供应商记录，解除等待';button.onclick=async()=>{const note=prompt('请填写核对结果（此操作不会自动重新出图）：');if(!note?.trim())return;try{await api(`/api/projects/${project.id}/operations/${problem.id}/acknowledge`,jsonOptions({checked_provider_records:true,note}));await refresh();}catch(e){say(e.message);}};$('operationError').append(button);}
  }
  $('modeInfo').replaceChildren();const strong=document.createElement('strong');strong.textContent=project?.provider==='openai'?'OpenAI 图片 API':'本地交互演示';$('modeInfo').append(strong,document.createTextNode(project?.provider==='openai'?`开发模式：不限制出图次数。已尝试 ${project.calls_used||0} 次；图片 API 仍按实际调用计费。`:'读取已有样例，不进行 AI 出图或修改。框选与反馈会保存，演示新版本不代表修改已生效。'));
  $('export').classList.toggle('disabled',!project);$('export').href=project?`/api/projects/${project.id}/export`:'#';
  $('history').replaceChildren();const versions=project?.revisions.filter(v=>v.stage===stage)||[];$('historyCount').textContent=versions.length;
  versions.forEach((v,i)=>{const b=document.createElement('button');b.className='version'+(r?.id===v.id?' selected':'');const img=document.createElement('img');img.src=v.image_url;img.alt=`${labels[stage]}版本 ${i+1}`;const text=document.createElement('span');text.textContent=`V${i+1} · ${v.stale?'已过期':v.approved?'已确认':'待确认'}`;b.append(img,text);b.onclick=()=>{selected=v.id;resetRegion();render();};$('history').append(b);});
  $('geometryPanel').hidden=true; // Model submission now belongs to phase 4.
  $('tripoBalance').textContent=tripoWallet?.configured?`API 积分余额：${tripoWallet.balance}。每次生成会消耗积分，第四步先为每个部件生成一个候选。`:'读取 Tripo API 余额中…';
  $('geometryGenerate').disabled=!r||!r.approved||r.stale||r.id!==project?.current[stage]||!region||busy||!!active||!(tripoWallet?.balance>0);
  $('geometryRecords').replaceChildren();for(const op of operations.filter(o=>o.kind==='geometry'&&o.stage===stage)){const div=document.createElement('div');div.className='operation';div.textContent=`${op.status} · ${op.progress||0}% · 消耗积分：${op.consumed_credit??'待返回'}`;if(op.error){const error=document.createElement('p');error.textContent=op.error;div.append(error);}if(op.download_url){const link=document.createElement('a');link.textContent='下载 GLB 几何模型';link.href=op.download_url;div.append(link);}if(op.status==='unknown'&&op.provider_task_id){const button=document.createElement('button');button.textContent='查询原任务';button.onclick=async()=>{try{await api(`/api/projects/${project.id}/geometry/${op.id}/refresh`,{method:'POST'});await refresh();}catch(e){say(e.message);}};div.append(button);}$('geometryRecords').append(div);}
  renderComponents();renderQuality(r);renderModelLibrary();
  $('operations').replaceChildren();for(const op of [...operations].reverse()) {const e=document.createElement('div');e.className='operation';const states={queued:'等待执行',running:'出图中',succeeded:'已完成',failed:'失败',unknown:'结果待核对',acknowledged:'已人工核对'};e.textContent=`${labels[op.stage]}${op.kind==='geometry'?' · 三维几何':''} · ${states[op.status]}\n${op.provider==='demo'?'本地样例 · 无生成支出':'API 请求 · 实际金额未知'}${op.usage?'\n用量：'+JSON.stringify(op.usage):''}${op.provider_request_id?'\n请求：'+op.provider_request_id:''}${op.provider_task_id?'\n任务：'+op.provider_task_id:''}`;e.style.whiteSpace='pre-wrap';if(op.prompt){const detail=document.createElement('details');const summary=document.createElement('summary');summary.textContent='本次完整提示词';const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';pre.textContent=op.prompt;detail.append(summary,pre);e.append(detail);}$('operations').append(e);}
}
async function submitComponents(pid,rid){
  const payload={turnaround_revision:rid};
  localStorage.setItem('pending-components-'+pid,JSON.stringify(payload));
  const batch=await api(`/api/projects/${pid}/generate-components`,jsonOptions(payload));
  localStorage.removeItem('pending-components-'+pid);
  const errors=batch.results.filter(v=>v.error);
  say(errors.length?errors.map(v=>labels[v.stage]+': '+v.error).join('\n'):'头部、身体和头发已并行提交，完成后会自动检查。');
}
function renderComponents(){
  const authority=project?.memory?.authoritative_turnaround;
  $('componentsPanel').hidden=!authority||!['turnaround','head','body','hair'].includes(stage);
  $('componentStates').replaceChildren();
  if(!authority)return;
  for(const part of ['head','body','hair']){
    const status=workflowState(part).text;
    const button=document.createElement('button');button.textContent=labels[part]+' · '+status;button.disabled=busy;button.onclick=()=>{stage=part;selected=project.current[part]||null;resetRegion();feedbackImages=[];$('feedback').value='';render();};$('componentStates').append(button);
  }
  $('generateComponents').disabled=busy||project.operations.some(o=>['queued','running','unknown'].includes(o.status));
}
function hasReviewFeedback(r){
  const q=r?.quality_review;
  return !r?.stale&&q?.status==='completed'&&q.source_revision===r.id&&q.authority_revision===project?.memory?.authoritative_turnaround?.revision_id&&!!q.findings?.length;
}
function renderQuality(r){
  $('reviewCombineHint').hidden=!hasReviewFeedback(r);
  const q=r?.quality_review;$('qualityPanel').hidden=!['head','body','hair'].includes(stage)||!q;
  $('qualityResult').replaceChildren();if(!q)return;
  const p=document.createElement('p');p.textContent=q.status==='running'?'AI 检查中':q.status==='completed'?(q.verdict==='pass'?'未发现明显问题':'需要人工检查')+': '+q.summary:q.summary;$('qualityResult').append(p);
  for(const finding of q.findings||[]){const item=document.createElement('p');item.textContent=`${finding.view} · ${finding.severity}: ${finding.description}`;const button=document.createElement('button');button.className='secondary';button.textContent='使用此修改建议';button.onclick=()=>{$('feedback').value=finding.suggested_change;$('feedback').focus();};item.append(button);$('qualityResult').append(item);}
}
$('generateComponents').onclick=async()=>{const rid=project?.memory?.authoritative_turnaround?.revision_id;if(!rid||busy)return;busy=true;render();try{await submitComponents(project.id,rid);await refresh();}catch(e){say(e.message);}finally{busy=false;render();}};
function renderViews(r){
  const multi=stage!=='design'&&!!r;
  $('viewsPanel').hidden=!multi;
  $('restartDesign').hidden=stage!=='turnaround';
  $('restartDesign').disabled=busy||project?.operations?.some(o=>['queued','running','unknown'].includes(o.status));
  $('sheetStage').hidden=multi&&!sheetOpen;
  document.querySelector('.annotation-toolbar').hidden=multi&&!sheetOpen;
  $('viewCards').replaceChildren();
  if(!multi)return;
  const names={front:'Front · 正面',back:'Back · 背面',left:'Left · 左侧',right:'Right · 右侧'};
  for(const view of ['front','back','left','right']){
    const asset=r.views?.find(v=>v.view===view);
    const card=document.createElement('button');card.className='view-card';card.disabled=!asset;
    const label=document.createElement('strong');label.textContent=names[view];card.append(label);
    if(asset){const img=document.createElement('img');img.src=asset.image_url;img.alt=names[view];card.append(img);card.onclick=()=>{$('viewTitle').textContent=names[view];$('viewLarge').src=asset.image_url;$('viewLarge').alt=names[view];$('viewDialog').showModal();};}
    else {const note=document.createElement('p');note.textContent='等待拆分';card.append(note);}
    $('viewCards').append(card);
  }
  $('splitMessage').textContent=r.view_split?.status==='ready'?'已自动拆分并保存方向标签；图片内容仍需人工检查。':r.view_split?.error||'此历史版本尚未拆分，请先自动拆分。';
  $('splitViews').hidden=r.view_split?.status==='ready';$('splitViews').disabled=busy||project?.operations?.some(o=>['queued','running','unknown'].includes(o.status));
  $('toggleSheet').textContent=sheetOpen?'收起原图':'查看原图／圈画修改';
}
$('restartDesign').onclick=()=>{stage='design';selected=project.current.design||null;designMode='text';baseImageId=null;feedbackImages=[];sheetOpen=false;resetRegion();$('feedback').value='';render();say('已回到整体设计，切换为文字生成。可重新填写要求出图；历史版本保留，新图生成成功后下游参考将过期。');$('feedback').focus();};
$('toggleSheet').onclick=()=>{sheetOpen=!sheetOpen;render();drawSelection();};
$('closeView').onclick=()=>$('viewDialog').close();
$('splitViews').onclick=async()=>{if(!shown()||busy)return;busy=true;render();try{await api(`/api/projects/${project.id}/revisions/${shown().id}/split`,{method:'POST'});await refresh();say('拆分结果已保存，请检查四个视图。');}catch(e){say(e.message);}finally{busy=false;render();}};
async function refresh(){if(!project)return;const pid=project.id;const before=project.current[stage];const next=await api(`/api/projects/${pid}`);if(project?.id!==pid)return;if(selected===before||!selected)selected=next.current[stage]||null;project=next;const pending=pendingRequest();if(pending&&next.operations.some(o=>o.request_id===pending.request_id))localStorage.removeItem('pending-generation-'+project.id);render();}
function showCreate(){$('provider').value=config?.default_provider||'demo';$('provider').onchange();$('createError').textContent='';$('createDialog').showModal();}
$('newProject').onclick=showCreate;$('emptyCreate').onclick=showCreate;$('closeDialog').onclick=()=>$('createDialog').close();
$('provider').onchange=()=>{$('providerHelp').textContent=$('provider').value==='openai'?'点击出图会发送设计和参考图到 OpenAI，并产生 API 费用。开发阶段不限制次数，不会自动重试付费请求。':'演示模式读取已有样例图，用来测试上传、反馈与确认流程；不会真正生成或修改图片。';};
$('projects').onchange=async()=>{try{await loadProject($('projects').value);say('');}catch(e){say(e.message);}};
$('createForm').onsubmit=async event=>{event.preventDefault();$('createSubmit').disabled=true;try{const form=new FormData();form.set('name',$('name').value);form.set('brief',$('brief').value);form.set('provider',$('provider').value);const p=await api('/api/projects',{method:'POST',body:form});stage='design';await loadProject(p.id);if($('initialImage').files[0]){const upload=new FormData();upload.set('purpose','base');upload.set('image',$('initialImage').files[0]);await api(`/api/projects/${p.id}/references`,{method:'POST',body:upload});await loadProject(p.id);}await loadProjects();$('createDialog').close();$('createForm').reset();say('角色任务已创建。请先确认整体设计。');}catch(e){$('createError').textContent=e.message;}finally{$('createSubmit').disabled=false;}};
$('generate').onclick=async()=>{
  if(busy||!project)return;
  const textOnly=stage==='design'&&designMode==='text';
  const r=textOnly||baseImageId&&stage==='design'||shown()?.stale?null:shown();
  if(!pendingRequest()&&stage==='design'&&designMode==='image'&&!r&&!baseImageId){say('请上传初始图片，或选择当前整体设计。');return;}
  if(!pendingRequest()&&r&&!$('feedback').value.trim()&&!feedbackImages.length&&!hasReviewFeedback(r)){say('填写修改意见或上传修改参考图片，再生成新版本。');$('feedback').focus();return;}
  busy=true;render();
  try{
    const payload=pendingRequest()||{stage,design_mode:stage==='design'?designMode:null,input_image_id:stage==='design'&&!textOnly?baseImageId:null,feedback_image_ids:textOnly?[]:feedbackImages.map(a=>a.id),feedback:$('feedback').value,source_revision:r?.id||null,region:r?region:null,brush_strokes:r?brushStrokes:[],request_id:crypto.randomUUID()};
    localStorage.setItem('pending-generation-'+project.id,JSON.stringify(payload));
    await api(`/api/projects/${project.id}/generate`,jsonOptions(payload));localStorage.removeItem('pending-generation-'+project.id);
    feedbackImages=[];
    say(project.provider==='demo'?'已记录文字与图片参考，正在读取演示样例；不会实际修改图片。':'已提交一次出图请求，文字与图片参考已一起提交。');await refresh();
  }catch(e){if(e.httpStatus)localStorage.removeItem('pending-generation-'+project.id);say(e.message);await refresh().catch(()=>{});}finally{busy=false;render();}
};
async function reopenCurrentReference(){
 const r=shown();if(!r?.approved||busy)return;
 busy=true;render();
 try{await api(`/api/projects/${project.id}/reopen/${r.id}`,{method:'POST'});await refresh();say('已返回修改状态，图片与历史版本保留。修改后可再次确认。');}
 catch(error){say(error.message);}finally{busy=false;render();}
};
$('approve').onclick=async()=>{
  const r=shown();if(!r||busy||r.stale)return;
  if(r.approved){if(approvalSettled)return reopenCurrentReference();return;}
  if(pendingRequest()){say('请先核对尚未完成的生成提交。');return;}
  const pid=project.id, approvedStage=stage;
  busy=true;render();
  try{
    const approval=await api(`/api/projects/${pid}/approve/${r.id}`,{method:'POST'});
    await refresh();
    const next=Object.keys(labels)[Object.keys(labels).indexOf(approvedStage)+1];
    if(next&&stepUnlocked(next)){stage=next;selected=project.current[stage]||null;resetRegion();feedbackImages=[];baseImageId=null;$('feedback').value='';render();}
    if(approvedStage==='design'){
      const payload={stage:'turnaround',feedback:'',source_revision:null,request_id:`auto-turnaround-${r.id}`};
      localStorage.setItem('pending-generation-'+pid,JSON.stringify(payload));
      try{
        await api(`/api/projects/${pid}/generate`,jsonOptions(payload));
        localStorage.removeItem('pending-generation-'+pid);
        say(project.provider==='demo'?'整体设计已确认，正在读取四视图演示样例。':'整体设计已确认，已自动提交四视图生成请求。');
      }catch(e){
        if(e.httpStatus)localStorage.removeItem('pending-generation-'+pid);
        say(e.message);
      }
      await refresh();
    }else if(approvedStage==='turnaround'){
      await submitComponents(pid,r.id);await refresh();
    }else if(stepUnlocked('models')){
      stage='models';selected=null;resetRegion();$('feedback').value='';
      const results=approval.model_submission;
      const errors=results?.results?.filter(v=>v.error)||[];
      say(results?.error||errors.map(v=>labels[v.stage]+': '+v.error).join('\n')||(config.tripo_configured?'三个部件已确认，已并行提交 3D 生成任务。':'三个部件已确认，请配置 Tripo API 后开始模型生成。'));
      render();
    }else say('当前版本已确认。');
  }catch(e){say(e.message);}finally{busy=false;render();}
};
$('upload').onchange=async()=>{const file=$('upload').files[0];if(!file||!project)return;busy=true;render();try{const data=new FormData();data.set('stage',stage);data.set('image',file);await api(`/api/projects/${project.id}/upload`,{method:'POST',body:data});selected=null;await refresh();say('新参考已上传，请检查后确认。');}catch(e){say(e.message);}finally{busy=false;$('upload').value='';render();}};
function showReferences(target, images, removable=false){
  $(target).replaceChildren();
  images.forEach(a=>{const card=document.createElement('div');card.className='reference-preview';const img=document.createElement('img');img.src=a.image_url;img.alt=a.name;const name=document.createElement('span');name.textContent=a.name;card.append(img,name);if(removable){const remove=document.createElement('button');remove.textContent='×';remove.setAttribute('aria-label','移除参考 '+a.name);remove.disabled=busy;remove.onclick=()=>{feedbackImages=feedbackImages.filter(v=>v.id!==a.id);render();};card.append(remove);}$(target).append(card);});
}
$('textMode').onclick=()=>{designMode='text';resetRegion();render();};
$('imageMode').onclick=()=>{designMode='image';resetRegion();render();};
$('useCurrent').onclick=()=>{baseImageId=null;resetRegion();render();};
async function attachImages(input,purpose){
  try{await attachImageFiles([...input.files],purpose,input);}finally{input.value='';}
}
async function attachImageFiles(files,purpose,input){
  if(!files.length)return;
  if(!project||busy||input.disabled){say('请先等待或核对当前操作');return;}
  if(purpose==='feedback'&&feedbackImages.length+files.length>3){say('每次修改最多使用 3 张参考图片。');return;}
  if(files.some(file=>!['image/png','image/jpeg','image/webp'].includes(file.type)&&!(file.type===''&&/\.(png|jpe?g|webp)$/i.test(file.name)))){say('只支持 PNG、JPEG、WebP');return;}
  if(files.some(file=>file.size>15*1024*1024)){say('图片不能超过 15 MB');return;}
  busy=true;render();try{for(const file of files){const form=new FormData();form.set('image',file);form.set('purpose',purpose);const asset=await api(`/api/projects/${project.id}/references`,{method:'POST',body:form});if(purpose==='base'){baseImageId=asset.id;designMode='image';resetRegion();}else feedbackImages.push(asset);}await refresh();say('参考图片已上传；点击生成时才会调用图片服务。');}catch(e){say(e.message);}finally{busy=false;render();}
}
let feedbackDragDepth=0;
function clearFeedbackDrag(){feedbackDragDepth=0;$('feedbackDropZone').classList.remove('drag-over');}
function isFileDrag(event){return [...(event.dataTransfer?.types||[])].includes('Files');}
const feedbackDrop=$('feedbackReferences');
feedbackDrop.addEventListener('dragenter',event=>{
  if(!isFileDrag(event))return;event.preventDefault();
  if($('feedbackUpload').disabled)return;
  feedbackDragDepth++;$('feedbackDropZone').classList.add('drag-over');
});
feedbackDrop.addEventListener('dragover',event=>{
  if(!isFileDrag(event))return;event.preventDefault();
  event.dataTransfer.dropEffect=$('feedbackUpload').disabled?'none':'copy';
});
feedbackDrop.addEventListener('dragleave',event=>{
  if(!isFileDrag(event))return;
  feedbackDragDepth=Math.max(0,feedbackDragDepth-1);if(!feedbackDragDepth)clearFeedbackDrag();
});
feedbackDrop.addEventListener('drop',async event=>{
  if(!isFileDrag(event))return;event.preventDefault();clearFeedbackDrag();
  await attachImageFiles([...event.dataTransfer.files],'feedback',$('feedbackUpload'));
});
$('feedbackDropZone').addEventListener('click',event=>{if($('feedbackUpload').disabled)event.preventDefault();});
$('feedbackDropZone').addEventListener('keydown',event=>{
  if(['Enter',' '].includes(event.key)){event.preventDefault();if(!$('feedbackUpload').disabled)$('feedbackUpload').click();}
});
// A file dropped outside the upload area must not navigate away from unsaved feedback.
for(const name of ['dragover','drop'])document.addEventListener(name,event=>{
  if(isFileDrag(event)){event.preventDefault();if(name==='drop')clearFeedbackDrag();}
});
window.addEventListener('blur',clearFeedbackDrag);
$('geometryGenerate').onclick=async()=>{if(!region||!current()||busy)return;busy=true;render();try{const key='pending-geometry-'+project.id;let payload=JSON.parse(localStorage.getItem(key)||'null');if(!payload){payload={stage,source_revision:current().id,crop:region,request_id:crypto.randomUUID()};localStorage.setItem(key,JSON.stringify(payload));}await api(`/api/projects/${project.id}/geometry`,jsonOptions(payload));localStorage.removeItem(key);say('已提交一个无材质几何任务，不会自动生成材质。');await refresh();}catch(e){if(e.httpStatus)localStorage.removeItem('pending-geometry-'+project.id);say(e.message);}finally{busy=false;render();}};
$('baseUpload').onchange=()=>attachImages($('baseUpload'),'base');
$('feedbackUpload').onchange=()=>attachImages($('feedbackUpload'),'feedback');
document.querySelectorAll('[data-hint]').forEach(b=>b.onclick=()=>{$('feedback').value=b.dataset.hint;$('feedback').focus();});
const canvas=$('selectionCanvas');
function drawSelection(){
  const rect=canvas.getBoundingClientRect();canvas.width=Math.round(rect.width*devicePixelRatio);canvas.height=Math.round(rect.height*devicePixelRatio);
  const ctx=canvas.getContext('2d');ctx.scale(devicePixelRatio,devicePixelRatio);ctx.clearRect(0,0,rect.width,rect.height);
  if(region){ctx.fillStyle='rgba(66,112,81,.14)';ctx.strokeStyle='#467454';ctx.lineWidth=2;ctx.setLineDash([6,4]);ctx.fillRect(region.x*rect.width,region.y*rect.height,region.width*rect.width,region.height*rect.height);ctx.strokeRect(region.x*rect.width,region.y*rect.height,region.width*rect.width,region.height*rect.height);}
  ctx.setLineDash([]);ctx.strokeStyle='#ef4444';ctx.fillStyle='#ef4444';ctx.lineCap='round';ctx.lineJoin='round';
  for(const stroke of brushStrokes){ctx.lineWidth=Math.max(2,stroke.width*Math.min(rect.width,rect.height));ctx.beginPath();stroke.points.forEach((p,i)=>i?ctx.lineTo(p.x*rect.width,p.y*rect.height):ctx.moveTo(p.x*rect.width,p.y*rect.height));ctx.stroke();if(stroke.points.length===1){const p=stroke.points[0];ctx.beginPath();ctx.arc(p.x*rect.width,p.y*rect.height,ctx.lineWidth/2,0,2*Math.PI);ctx.fill();}}
  $('selectionHint').textContent=brushStrokes.length?`已圈画 ${brushStrokes.length} 笔，提交时会把标注图与文字一起发送。`:region?'已框选修改区域，可重新拖动或清除。':'用画笔直接圈出问题，再写明如何修改。';
  $('undoStroke').disabled=!brushStrokes.length||busy;
  $('geometryGenerate').disabled=!config?.tripo_configured||!current()?.approved||!region||busy||!(tripoWallet?.balance>0)||project?.operations?.some(o=>['queued','running','unknown'].includes(o.status));
}
function point(event){const r=canvas.getBoundingClientRect();return {x:Math.min(1,Math.max(0,(event.clientX-r.left)/r.width)),y:Math.min(1,Math.max(0,(event.clientY-r.top)/r.height))};}
function mayAnnotate(){return shown()&&!shown().stale&&shown().id===project?.current[stage]&&!busy&&!project?.operations?.some(o=>['queued','running','unknown'].includes(o.status));}
canvas.onpointerdown=e=>{
  if(!mayAnnotate())return;
  if(stage==='design'){designMode='image';baseImageId=null;render();}
  drawing=point(e);canvas.setPointerCapture(e.pointerId);
  if(annotationTool==='brush'){if(brushStrokes.length>=100){drawing=null;say('标注笔数已达上限，请清除或简化。');return;}currentStroke={width:.006,points:[drawing]};brushStrokes.push(currentStroke);drawSelection();}
};
canvas.onpointermove=e=>{
  if(!drawing)return;const p=point(e);
  if(annotationTool==='brush'){if(currentStroke&&currentStroke.points.length<2000){const last=currentStroke.points.at(-1);if(Math.hypot(p.x-last.x,p.y-last.y)>.0015)currentStroke.points.push(p);}}
  else region={x:Math.min(drawing.x,p.x),y:Math.min(drawing.y,p.y),width:Math.abs(p.x-drawing.x),height:Math.abs(p.y-drawing.y)};
  drawSelection();
};
canvas.onpointerup=()=>{drawing=null;currentStroke=null;if(region&&(region.width<.01||region.height<.01))region=null;drawSelection();};
canvas.onpointercancel=()=>{drawing=null;currentStroke=null;};
$('brushTool').onclick=()=>{annotationTool='brush';region=null;render();drawSelection();};
$('boxTool').onclick=()=>{annotationTool='box';render();drawSelection();};
$('undoStroke').onclick=()=>{brushStrokes.pop();drawSelection();};
$('clearSelection').onclick=resetRegion;$('referenceImage').onload=drawSelection;new ResizeObserver(drawSelection).observe($('imageWrap'));
async function start(){try{config=await api('/api/config');promptTemplates=await api('/api/prompts');if(config.providers.includes('openai'))$('provider').add(new Option('OpenAI API · 付费出图','openai'));if(config.tripo_configured)api('/api/services/tripo/balance').then(wallet=>{tripoWallet=wallet;render();}).catch(e=>say(e.message));const list=await loadProjects();const remembered=localStorage.getItem('reference-project');if(list.length)await loadProject(list.find(p=>p.id===remembered)?.id||list[0].id);else render();}catch(e){say(e.message);}}
setInterval(()=>{if(project)refresh().catch(e=>say('连接暂时中断；恢复后会继续读取任务状态。'));},2000);start();
