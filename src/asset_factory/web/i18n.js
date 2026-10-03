/* UI-only translations. Project names, user inputs and prompt snapshots stay intact. */
const translations = {
'点击出图会发送设计和参考图到 OpenAI，并产生 API 费用。开发阶段不限制次数，不会自动重试付费请求。':'Generating sends your design and references to OpenAI and incurs API fees. Development mode has no attempt limit. Paid requests are not automatically retried.',
'角色参考工作室':'Character Reference Studio','＋ 新角色':'+ New character','开始一个新角色':'Start a new character','先确认设计，再逐步准备可用于三维生成的参考。':'Approve the design, then prepare references for 3D modeling.',
'整体设计':'Overall design','四视图':'Four views','头部':'Head','身体与服装':'Body & outfit','头发':'Hair','已确认':'Approved','等待确认':'Awaiting approval','上游已变更':'Upstream changed','尚未解锁':'Locked','等待参考':'Awaiting reference','需更新':'Needs update','历史版本':'Previous version','待确认':'Awaiting approval','待生成':'Not generated','待创建':'Not created','已过期':'Outdated',
'请按顺序确认前面的步骤':'Approve the previous steps first','参考图步骤':'Reference steps','选择角色':'Select character','每次修改都保留版本':'Every change keeps a version','上游设计变更后，下游参考会标记为待更新。':'When an upstream design changes, downstream references become outdated.',
'确定角色的轮廓、配色和服装。':'Define the silhouette, colors and outfit.','让正面、侧面和背面的设计保持一致。':'Keep the front, side and back views consistent.','准备不含头发的头部参考，保留脸部身份。':'Prepare a bald head reference while preserving facial identity.','分清服装、皮肤与装饰，让轮廓可读。':'Keep clothing, skin and accessories distinct.','独立展示发型结构、发束和饰品。':'Show the hair structure, strands and accessories separately.',
'下载参考包 ↗':'Download reference pack ↗','等待第一张参考图':'Awaiting the first reference','从一个角色想法开始':'Start with a character idea','写下你的设计，也可以直接上传已有参考图。':'Describe your design or upload an existing reference.','创建角色':'Create character','版本记录':'Version history','当前角色参考图':'Current character reference','在参考图上圈画或框选修改区域':'Draw or select an area to edit','图片标注工具':'Image annotation tools','画笔圈画':'Draw marks','框选区域':'Select area','撤销一笔':'Undo stroke','清除标注':'Clear marks','可以在图上拖动，框出需要调整的区域。':'Drag on the image to select an area to edit.','用画笔直接圈出问题，再写明如何修改。':'Mark the issue, then describe the change.',
'哪里需要调整？':'What needs changing?','在图上圈出问题，再写明怎么改。标注图与文字会一起提交，原图保留。':'Mark the issue and describe the change. Your annotation and text are submitted together; the original is kept.','整体设计生成模式':'Design generation mode','文字生成':'From text','已有图像生成':'From an image','根据角色设计和文字要求生成新的整体设计，不使用当前图片。':'Generate a new design from the character brief and your text, without using the current image.','使用上传的初始图片或当前版本，再结合文字和修改参考图片生成。':'Use an uploaded image or the current version, together with text and change references.',
'＋ 上传初始图片':'+ Upload source image','使用当前整体设计作为初始图':'Use the current design as the source','修改意见／生成要求':'Changes / generation instructions','例如：背面的交叉背带保留，下面应是白色衬衫，不是裸露皮肤。其他部分保持不变。':'Example: Keep the crossed straps on the back. The area underneath should be a white shirt, not exposed skin. Keep everything else unchanged.','＋ 上传修改参考图片（最多 3 张）':'+ Upload change references (up to 3)','例如服装、发型或细节示意图。上传后随本次意见一起提交。':'For example, outfit, hair or detail references. They will be submitted with these instructions.','本步骤生成规则':'Generation rules for this step','调整比例':'Adjust proportions','视图一致':'Consistent views','轮廓清楚':'Clear silhouette',
'保持角色身份和配色，调整比例，让头、身体和四肢更协调。':'Preserve identity and colors; adjust the head, body and limb proportions.','保持角色外观，让四个视角的衣服和发型细节一致。':'Preserve the character and keep outfit and hair details consistent across all four views.','保持设计，移除背景和遮挡，让零件轮廓更清楚。':'Preserve the design; remove background clutter and occlusion to clarify the component silhouette.',
'生成参考图':'Generate reference','根据文字生成整体设计':'Generate design from text','根据初始图片生成':'Generate from source image','根据新设计重新生成':'Regenerate from updated design','根据意见生成新版本':'Generate a revised version','确认这张图':'Approve this image','确认并生成四视图':'Approve & generate four views','请先核对尚未完成的生成提交。':'Resolve the pending generation request first.','整体设计已确认，正在读取四视图演示样例。':'Design approved. Loading the four-view demo sample.','整体设计已确认，已自动提交四视图生成请求。':'Design approved. Four-view generation submitted automatically.','确认四视图并继续':'Approve four views and continue','↑ 上传此步骤的参考图':'↑ Upload a reference for this step','核对并重发原提交':'Check and resend original request',
'本地交互演示':'Local workflow demo','读取已有样例，不进行 AI 出图或修改。框选与反馈会保存，演示新版本不代表修改已生效。':'Replays local samples without AI generation or editing. Selections and feedback are saved; new demo versions do not represent actual edits.','OpenAI 图片 API':'OpenAI Image API','出图记录':'Generation log','本次完整提示词':'Full prompt for this request','已核对供应商记录，解除等待':'I checked the provider records; resolve the pending status','请填写核对结果（此操作不会自动重新出图）：':'Enter the verification result (this will not generate another image):',
'重新开始整体设计':'Restart overall design','逐张检查朝向、站姿、手脚和头发是否完整。点击图片可放大查看。':'Check each view’s direction, pose, hands, feet and hair. Click an image to enlarge it.','Front · 正面':'Front','Back · 背面':'Back','Left · 左侧':'Left','Right · 右侧':'Right','等待拆分':'Awaiting split','已自动拆分并保存方向标签；图片内容仍需人工检查。':'Views were split and tagged automatically. Please review the image content.','此历史版本尚未拆分，请先自动拆分。':'This version has not been split yet. Split it first.','自动拆分当前四视图':'Split this four-view sheet','查看原图／圈画修改':'View original / mark changes','收起原图':'Hide original','关闭':'Close','需要修改时，返回原图圈画，并在修改意见中注明此视图。':'To make changes, mark the original sheet and mention this view in your instructions.','拆分结果已保存，请检查四个视图。':'The split views were saved. Please review all four.',
'正在生成图片…':'Generating images…','请求已提交，等待生成…':'Request submitted. Waiting to generate…','正在处理请求…':'Processing your request…','模型正在处理，结果返回后会自动更新。请勿重复提交。':'The model is processing your request. Results will appear automatically. Please do not submit again.','正在提交或保存，请稍候。':'Submitting or saving. Please wait.','模型正在处理，请稍候。':'The model is processing. Please wait.','正在准备新版本':'Preparing a new version','可以刷新页面，任务记录会保留。':'You can refresh the page; your task records are saved.',
'创建一个角色':'Create a character','角色名称':'Character name','例如：星光女仆':'Example: Starlight maid','角色设计':'Character brief','角色设计（选填）':'Character brief (optional)','描述角色的风格、发型、服装、配色和需要保留的细节。':'Describe the style, hair, outfit, colors and details to preserve.','出图方式':'Generation provider','最多出图次数':'Maximum generation attempts','已有整体参考（可选）':'Existing design reference (optional)','进入参考工作室 →':'Enter Reference Studio →','本地交互演示 · 不调用 AI':'Local demo · No AI calls','OpenAI API · 付费出图':'OpenAI API · Paid generation','点击出图会发送设计和参考图到 OpenAI，并产生 API 费用。次数上限不是美元预算，不会自动重试付费请求。':'Generating sends your design and references to OpenAI and incurs API fees. The attempt limit is not a dollar budget. Paid requests are not automatically retried.','演示模式读取已有样例图，用来测试上传、反馈与确认流程；不会真正生成或修改图片。':'Demo mode replays samples to test upload, feedback and approval; it does not generate or edit images.',
'角色任务已创建。请先确认整体设计。':'Character project created. Approve the overall design first.','请上传初始图片，或选择当前整体设计。':'Upload a source image or select the current design.','填写修改意见或上传修改参考图片，再生成新版本。':'Enter changes or upload references before generating a new version.','已记录文字与图片参考，正在读取演示样例；不会实际修改图片。':'Text and references saved. Loading a demo sample; no actual image editing.','已提交一次出图请求，文字与图片参考已一起提交。':'One generation request submitted with your text and image references.','当前版本已确认，已进入下一步。':'Version approved. Moved to the next step.','全部参考步骤已确认。':'All reference steps approved.','新参考已上传，请检查后确认。':'Reference uploaded. Review it before approval.','每次修改最多使用 3 张参考图片。':'Use up to 3 reference images per edit.','参考图片已上传；点击生成时才会调用图片服务。':'References uploaded. The image service is called only when you generate.','移除参考 ':'Remove reference ',
'已回到整体设计，切换为文字生成。可重新填写要求出图；历史版本保留，新图生成成功后下游参考将过期。':'Returned to overall design in text mode. Enter new instructions to generate. History is kept; downstream references become outdated after a new design is generated.','连接暂时中断；恢复后会继续读取任务状态。':'Connection interrupted. Task status will resume when the connection returns.','输入不完整或请求失败，请检查填写内容。':'Incomplete input or request failed. Please check your entries.','标注笔数已达上限，请清除或简化。':'Annotation limit reached. Clear or simplify your marks.','已框选修改区域，可重新拖动或清除。':'Edit area selected. Drag again or clear it.',
'等待执行':'Queued','出图中':'Generating','已完成':'Completed','失败':'Failed','结果待核对':'Result needs verification','已人工核对':'Manually verified','本地样例 · 无生成支出':'Local sample · No generation charge','API 请求 · 实际金额未知':'API request · Actual charge unknown','用量：':'Usage:','请求：':'Request:','任务：':'Task:',
'图片 API：已配置':'Image API: configured','图片 API：未配置':'Image API: not configured','3D 生成：暂停，当前仅调试图片流程':'3D generation: paused; image workflow only','读取本步骤规则中…':'Loading step instructions…',
'视图之间没有清楚的空白带，请修改布局后重新生成或上传':'No clear gap between views. Adjust the layout and regenerate or upload a corrected sheet.','视图间空白过窄，请增加留白':'The gap between views is too narrow. Add more space.','至少一个视图为空，请检查四宫格布局':'At least one view is empty. Check the grid layout.','图片过小，无法可靠拆分四视图':'Image too small to split reliably.','请先完成四视图拆分并检查裁切预览':'Split the sheet and review the crops before approval.','只能确认当前有效版本':'Only the current valid version can be approved.','已有进行中或结果未知的操作，请先处理':'A request is running or its outcome is unknown. Resolve it first.','已达到本任务的出图次数上限':'This project has reached its generation attempt limit.','请填写修改意见':'Enter the requested changes.','任务不存在':'Project not found.','请先等待或核对当前出图操作':'Wait for or verify the current generation request.','请先等待当前操作完成':'Wait for the current operation to finish.',
'API 密钥无效，请检查服务端配置。':'Invalid API key. Check the server configuration.','账号没有图片模型访问权限。':'This account cannot access the image model.','调用受限或余额不足，请检查账号。':'Rate limit or insufficient balance. Check your account.','图片请求参数或内容不被接受，请检查模型和输入。':'Image request rejected. Check the model and input.','图片服务返回错误，请核对调用记录。':'The image service returned an error. Check the request records.'
};
Object.assign(translations,{
 '项目包 · ZIP，包含可直接打开的 .blend、所选版本的参考图和 Codex 项目说明。解压即可使用。':'Project ZIP with a ready-to-open .blend, references for the selected versions and a Codex handoff guide. Extract and use.',
 '正在导出 Blender 文件，请稍候…':'Exporting Blender file. Please wait…',
 'Blender 文件已导出。':'Blender file exported.',
 '直接下载 Blender 文件（.blend），包含选中的三个部件与贴图；不自动对齐、拼接或绑定。':'Download a Blender file (.blend) with the three selected parts and packed textures. No automatic alignment, merging or rigging.',
 '直接下载 Blender 文件（.blend），包含模型与贴图。贴图生成是可选步骤。':'Download a Blender file (.blend) with the model and packed textures. Texturing is optional.',

 '当前浏览器不支持选择保存位置，将使用浏览器默认下载位置。支持此功能的浏览器中会弹出保存窗口。':'This browser cannot choose a save location and will use its default download location. Supported browsers show a Save dialog.',
 '项目导出包已保存到所选位置。':'Project package saved to the selected location.',
 '导出失败，请重试。':'Export failed. Please try again.',

 '导出此部件':'Export component',
 '导出项目':'Export project',
 '贴图模型':'Textured model',
 '白模':'White model',
 '导出版本':'Export version',
 '选择 Head、Body、Hair 的版本。默认优先使用贴图模型，没有贴图则使用白模。':'Choose Head, Body and Hair versions. Defaults to textured models when available, otherwise white models.',
 'Blender 导入包 · ZIP。可导入新场景或已有角色文件；不自动对齐、拼接或绑定。':'Blender import package · ZIP. Import into a new scene or an existing character file. No automatic alignment, merging or rigging.',
 'Blender 导入包 · ZIP。可导入新场景或已有角色文件；贴图生成是可选步骤。':'Blender import package · ZIP. Import into a new scene or an existing character file. Texturing is optional.',

 '生成贴图':'Generate texture',
 '贴图已提交':'Texture submitted',
 '白模和贴图模型均可直接导出 Blender 文件包；贴图生成是可选步骤。':'White and textured models can both be exported to Blender. Texture generation is optional.',"操作不存在": "Operation not found.", "服务重启，未开始的操作已停止，可重新提交。": "The server restarted. Requests that had not started were stopped and can be resubmitted.", "服务在请求期间中断，结果及扣费未知。请先核对供应商记录。": "The server stopped during the request. The result and billing are unknown. Check the provider records first.", "只支持 PNG、JPEG、WebP": "Only PNG, JPEG and WebP are supported.", "图片不能超过两千万像素": "Images must not exceed 20 million pixels.", "图片文件无法读取": "Unable to read the image file.", "未取得可确认的图片结果，扣费可能已发生。请核对供应商记录后再继续。": "No confirmed image result was received. Charges may have occurred. Check the provider records before continuing.", "请选择四视图版本": "Select a four-view version.", "该出图服务尚未配置": "This image provider is not configured.", "图片不能超过 15 MB": "Images must not exceed 15 MB.", "参考图类型无效": "Invalid reference type.", "本地处理失败，原版本保留；请核对记录。": "Local processing failed. The original version was kept. Check the records.", "参考图片不存在或不属于当前角色": "Reference not found or does not belong to this character.", "生成模式与初始图片仅适用于整体设计": "Generation mode and source images apply only to overall design.", "文字生成模式不使用图片，请切换已有图像生成": "Text mode does not use images. Switch to image mode.", "请上传初始图片或选择当前整体设计": "Upload a source image or select the current overall design.", "只能选择一张初始图片": "Select only one source image.", "请先生成并显示初始图片，再进行框选修改": "Generate and display the source image before selecting an edit area.", "修改源版本不存在、步骤不匹配或已过期": "The source version is missing, belongs to another step or is outdated.", "请基于当前版本修改，避免历史版本分支混淆": "Edit the current version to avoid conflicting history branches.", "框选修改需要已有图片": "Selecting an edit area requires an existing image.", "圈画修改需要当前有效版本作为原图": "Annotations require the current valid image as their source.", "圈画修改意见.png": "Annotated changes.png", "请先等待或核对当前操作": "Wait for or verify the current operation.", "请先核对供应商记录": "Check the provider records first.", "操作状态不允许解除": "This operation cannot be resolved in its current state.", "图片不存在": "Image not found.", "三维几何试运行": "3D geometry trial", "先确认此部件，再用框选工具选中一个完整正面视图，避免把整张多视图当成一个模型。": "Approve this component, then select one complete front view. Do not submit the whole sheet as one object.", "读取 Tripo API 余额中…": "Loading Tripo API balance…", "生成一个无材质几何候选": "Generate one untextured geometry candidate", "下载 GLB 几何模型": "Download GLB geometry", "查询原任务": "Query original task", "三维几何": "3D geometry", "已提交一个无材质几何任务，不会自动生成材质。": "One untextured geometry task submitted. Textures will not be generated automatically."});
Object.assign(translations,{"确认并生成三个部件": "Approve all views & generate components", "确认此部件": "Approve this component", "当前版本已确认。": "Current version approved.", "部件并行生成": "Parallel component generation", "生成／核对三个部件": "Generate / check three components", "AI 结构检查": "AI structure review", "检查只提供建议，请确认图片后继续。": "Review is advisory. Inspect the images before approval.", "AI 正在检查部件…": "AI is reviewing this component…", "正在检查结构分离、残留和颈部衔接，请稍候。": "Checking isolation, unwanted anatomy and neck interfaces. Please wait.", "AI 检查中": "AI review in progress", "生成中": "Generating", "未发现明显问题": "No obvious issues found", "需要人工检查": "Needs human review", "使用此修改建议": "Use this suggested change", "头部、身体和头发已并行提交，完成后会自动检查。": "Head, body and hair submitted in parallel. Each will be reviewed after generation.", "请先确认当前整体四视图": "Approve the current whole-character four views first."});
Object.assign(translations,{'3D 生成已暂停，正在核对 P2.0 接口。':'3D generation paused while the P2.0 API is being verified.'});
Object.assign(translations,{
 '正在提交贴图生成任务…':'Submitting texture generation…',
 '正在确认贴图模型…':'Approving textured model…',
 '并行部件':'Parallel components',
 '同时生成 · 各自检查与确认':'Generate together · Review separately',
 '部件已确认':'components approved',
 '确认整体四视图后，三个部件同时解锁':'Approve whole-character four views to unlock all three components.',
 'AI 检查不可用，请人工检查':'AI review unavailable; inspect manually',
 '视图待拆分检查':'View split needs inspection',
 '阶段 01 / 03':'PHASE 01 / 03',
 '阶段 02 / 03':'PHASE 02 / 03',
 '阶段 03 / 03 · 并行部件':'PHASE 03 / 03 · PARALLEL COMPONENTS',
 '确认设计与四视图后，头部、身体和头发并行准备。':'Approve the design and four views, then prepare head, body and hair in parallel.'
});
Object.assign(translations,{
 '拖拽图片到这里，或点击选择':'Drag images here, or click to browse',
 '松开即可上传修改参考图片':'Drop to upload change references'
});
Object.assign(translations,{
 '生成新版本时会自动结合此版本的 AI 检查建议与修改意见；有冲突时以你的意见为准。':'Revisions combine this version’s AI review with your changes. Your changes take priority if they conflict.'
});
Object.assign(translations,{
 '3D 模型检查与导出':'3D model review & export',
 '查看生成结果，确认后保存模型或导出 Blender 文件包。':'Inspect generated models, then approve to save or export a Blender package.',
 '打开本地 GLB 预览':'Open local GLB preview',
 '暂无生成结果。API 返回的模型会按部件列在这里；也可以打开本地 GLB 测试预览。':'No generated models yet. API results will appear here by component. You can also preview a local GLB.',
 '3D 模型预览':'3D model preview','本地 GLB 预览':'Local GLB preview',
 '侧面 A':'Side A','侧面 B':'Side B','重置视角':'Reset view',
 '拖动旋转，滚轮缩放。请检查完整性、缺失部件、穿插和材质；网页预览不能证明拓扑适合绑定。':'Drag to rotate; scroll to zoom. Check completeness, missing parts, intersections and materials. Preview does not establish rig-ready topology.',
 '检查完成，确认此模型':'Review complete · Approve model',
 '下载 GLB 到本地':'Save GLB locally','导出 Blender 文件包':'Export Blender package',
 '确认后可导出。Blender 文件包包含模型和导入脚本，不会自动拼接或绑定。':'Export after approval. The Blender package includes the model and an import script; assembly and rigging remain manual.',
 '当前仅预览本地文件，未上传或保存到角色项目。':'Local preview only. This file has not been uploaded or saved to the character project.',
 '模型已确认':'Model approved','等待模型检查':'Awaiting model review','查看 3D 模型':'View 3D model',
 '正在加载 3D 模型…':'Loading 3D model…','模型已加载，可以旋转检查。':'Model loaded. Rotate it to inspect.',
 '模型预览组件未就绪，请安装网页依赖或检查服务。':'Viewer unavailable. Install the web dependencies or check the service.',
 '模型加载失败，请检查文件或重新下载原任务结果。':'Model failed to load. Check the file or download the original task result again.',
 '模型已确认，可下载或导出。':'Model approved. Download or export is available.',
 '模型参考已变更，请重新检查当前版本':'Model reference changed. Review the current version.',
 '模型文件不是有效的 GLB':'The file is not a valid GLB.','模型文件无法读取':'Unable to read the model file.',
 '请选择不超过 100 MB 的 GLB 文件。':'Choose a GLB file up to 100 MB.'
});
Object.assign(translations,{'正面':'Front','背面':'Back','可旋转查看的 3D 模型':'Interactive 3D model'});
Object.assign(translations,{
 '3D 生成':'3D generation','三个部件并行生成，完成后检查并导出模型。':'Generate all three components in parallel, then inspect and export the models.',
 '阶段 01 / 04':'PHASE 01 / 04','阶段 02 / 04':'PHASE 02 / 04','阶段 03 / 04 · 并行部件':'PHASE 03 / 04 · PARALLEL COMPONENTS','阶段 04 / 04':'PHASE 04 / 04',
 '开始并行生成三个模型':'Generate three models in parallel','三个模型已提交':'Three models submitted',
 '等待模型生成':'Awaiting model generation','无材质几何候选':'Untextured geometry candidate',
 '请配置 Tripo API 后开始模型生成。':'Configure the Tripo API to start model generation.',
 '三个部件已确认，请配置 Tripo API 后开始模型生成。':'All components approved. Configure the Tripo API to start generating models.',
 '三个部件已确认，已并行提交 3D 生成任务。':'All components approved. 3D generation tasks submitted in parallel.',
 '已并行提交三个 3D 模型任务。':'Three 3D model tasks submitted in parallel.',
 '请先确认三个当前部件参考':'Approve all three current component references first.',
 '3D API：已配置':'3D API: configured','3D API：未配置':'3D API: not configured'
});
Object.assign(translations,{
 '生成设置：无材质四边形网格；Head 5,000 面，Body & outfit / Hair 20,000 面。保留原始 FBX，GLB 仅用于网页预览。':'Generation: untextured quad mesh. Head: 5,000 faces; Body & outfit / Hair: 20,000 faces. Original FBX preserved; GLB is a browser preview.',
 '下载原始 FBX 检查':'Download original FBX for inspection',
 '下载原始四边形 FBX':'Save original quad FBX',
 'FBX 网页预览需要本机 Blender；原文件已保存。':'FBX browser preview requires local Blender. The original file is saved.',
 '已在 Blender 检查，确认模型':'Inspected in Blender · Approve model',
 '请先下载原始 FBX 在 Blender 检查，再确认模型。':'Download and inspect the original FBX in Blender before approving it.'
});
Object.assign(translations,{
 '重新准备网页预览':'Prepare browser preview again',
 '未找到 Blender，原始四边形 FBX 已保留。可下载到 Blender 检查，或设置 BLENDER_BINARY 后重新准备预览。':'Blender was not found. The original quad FBX is preserved. Inspect it in Blender, or configure BLENDER_BINARY and prepare the preview again.',
 'FBX 预览转换失败，原始四边形文件保留。':'FBX preview conversion failed. The original quad file is preserved.',
 '预览正在准备，请稍候':'Preview is being prepared. Please wait.'
});
Object.assign(translations, {
 '旧设置模型 · GLB 三角网格':'Earlier settings · GLB triangle mesh', '四边形目标':'quad target', '3D 部件页面':'3D component pages', '头部 · 3D':'Head · 3D', '身体与服装 · 3D':'Body & outfit · 3D', '头发 · 3D':'Hair · 3D',
 '头部 · 3D 模型候选':'Head · 3D model candidates',
 '身体与服装 · 3D 模型候选':'Body & outfit · 3D model candidates',
 '头发 · 3D 模型候选':'Hair · 3D model candidates',
 '每个部件单独检查与确认；本页只展示该部件的候选版本。':'Inspect and approve each component separately. This page shows candidates for this component only.',
 '模型显示模式':'Model display modes', '灰模起伏':'Clay surface', '白模形状':'White model', '显示拓扑线':'Show topology edges', '原始材质':'Original materials', '线框叠加':'Wire overlay', '透视线框':'X-ray wire',
 '线框显示 GLB 的三角网格；原始 FBX 的四边形拓扑请在 Blender 核对。透视线框用于观察遮挡后的网格，不代表已有骨骼绑定。':'Wireframe shows GLB triangles. Check original FBX quads in Blender. X-ray reveals occluded mesh edges; it does not indicate rigging.'
});
Object.assign(translations, {
 '点击查看模型详情':'Click to inspect model', '正在加载模型缩略图…':'Loading model preview…', '模型已保存，网页预览暂不可用':'Model saved. Browser preview unavailable.',
 '等待模型生成':'Awaiting model generation', '缩略图加载失败，点击查看详情':'Preview unavailable. Click to inspect.',
 '头部 · 查看模型详情':'Head · Inspect model', '身体与服装 · 查看模型详情':'Body & outfit · Inspect model', '头发 · 查看模型详情':'Hair · Inspect model',
 '头部 · 模型缩略图':'Head · Model preview', '身体与服装 · 模型缩略图':'Body & outfit · Model preview', '头发 · 模型缩略图':'Hair · Model preview'
});
Object.assign(translations, {
 '输入：Front / Left / Back / Right 四张独立图':'Input: four separate Front / Left / Back / Right images',
 '输入：单张正面图（旧流程）':'Input: single Front image (earlier workflow)',
 '生成设置：无材质四边形网格；Head 5,000 面，Body & outfit / Hair 20,000 面。分别上传 Front / Left / Back / Right 四张部件视图。保留原始 FBX，GLB 仅用于网页预览。':'Generation: untextured quad mesh. Head: 5,000 faces; Body & outfit / Hair: 20,000 faces. Four separate Front / Left / Back / Right inputs. Original FBX preserved; GLB is a browser preview.',
 '鼠标左键拖动自由旋转，滚轮缩放，右键拖动平移。请检查完整性、缺失部件、穿插和材质；网页预览不能证明拓扑适合绑定。':'Left-drag to rotate freely; scroll to zoom; right-drag to pan. Inspect missing parts, intersections and materials. Preview does not establish rig-ready topology.'
});
Object.assign(translations, {
 '取消确认，继续修改':'Reopen for changes',
 '已返回修改状态，图片与历史版本保留。修改后可再次确认。':'Reopened for changes. Images and history are preserved. Approve again when ready.',
 '只能返回当前有效版本进行修改':'Only the current valid version can be reopened.',
 '请先等待或核对当前操作，再返回修改':'Wait for or resolve current operations before reopening.'
});
Object.assign(translations, {'网页线框显示渲染时的三角网格；原始 FBX 的四边形拓扑请在 Blender 核对。透视线框用于观察遮挡后的网格，不代表已有骨骼绑定。':'Browser wireframe shows render triangles. Check original FBX quads in Blender. X-ray reveals occluded mesh edges; it does not indicate rigging.'});
Object.assign(translations, {'下载原始 FBX':'Download original FBX', '四视图输入 · Front / Left / Back / Right':'4 views · Front / Left / Back / Right'});
let uiLanguage=localStorage.getItem('studio-language')==='en'?'en':'zh';
const originalText=new WeakMap(),originalAttributes=new WeakMap();
function translateUI(text){
 if(text.startsWith('项目文件名：'))return 'Project filename: '+text.slice('项目文件名：'.length);
 if(/^(贴图模型|白模) · /.test(text))return text.replace(/^(贴图模型|白模)/,value=>translations[value]);
 if(/ · 导出版本$/.test(text))return translateUI(text.replace(/ · 导出版本$/, ''))+' · Export version';
 if(/^3D 完成进度：\d+ \/ 3$/.test(text))return text.replace(/^3D 完成进度：(\d+) \/ 3$/,'3D models ready: $1 / 3');
 if(translations[text])return translations[text];
 if(text.includes('\n'))return text.split('\n').map(translateUI).join('\n');
 const space=text.match(/^(\s*)([\s\S]*?)(\s*)$/);if(space&&translations[space[2]])return space[1]+translations[space[2]]+space[3];
 if(/^开发模式：不限制出图次数。/.test(text))return text.replace(/^开发模式：不限制出图次数。已尝试 (\d+) 次；图片 API 仍按实际调用计费。$/,'Development mode: no attempt limit. Attempts: $1. Image API calls are still billed.');
 if(/^已等待 \d+ 秒$/.test(text))return text.replace(/^已等待 (\d+) 秒$/,'Waiting: $1 s');
 if(/^已圈画 \d+ 笔/.test(text))return text.replace(/^已圈画 (\d+) 笔，提交时会把标注图与文字一起发送。$/,'$1 strokes marked. The annotated image and text will be submitted together.');
 if(/^点击出图会调用付费 API。/.test(text))return text.replace(/^点击出图会调用付费 API。已尝试 (\d+) \/ (\d+) 次；实际美元费用尚未结算。$/,'Generating incurs API fees. Attempts: $1 / $2. Actual dollar charges are not yet confirmed.');
 if(/^移除参考 /.test(text))return 'Remove reference '+text.slice(5);
 if(/^请先确认有效的/.test(text))return 'Approve a valid '+translateUI(text.slice('请先确认有效的'.length))+' first.';
 // Composite labels and log lines contain app-generated counters and identifiers.
 if(/^(未发现明显问题|需要人工检查|整体设计|四视图|头部|身体与服装|头发|V\d+|API 请求|本地样例|用量：|请求：|任务：)/.test(text)){
  let output=text;for(const key of Object.keys(translations).sort((a,b)=>b.length-a.length))output=output.split(key).join(translations[key]);return output.replace(/版本 (\d+)/g,' version $1');
 }
 return text;
}
function applyUILanguage(){
 const skip='#projectName,#projects,#promptPreview,#operations pre,textarea,input';
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 let node;while(node=walker.nextNode()){
  if(node.parentElement?.closest(skip)||node.parentElement?.closest('script,style'))continue;
  const previous=originalText.get(node);const source=previous&&node.textContent===previous.output?previous.source:node.textContent;
  const output=uiLanguage==='en'?translateUI(source):source;
  originalText.set(node,{source,output});if(node.textContent!==output)node.textContent=output;
 }
 for(const element of document.querySelectorAll('[placeholder],[aria-label],[title],[data-hint],img[alt]')){
  if(element.closest('#projectName'))continue;
  const records=originalAttributes.get(element)||{};
  for(const attr of ['placeholder','aria-label','title','alt','data-hint']){
   if(!element.hasAttribute(attr))continue;const value=element.getAttribute(attr),old=records[attr];const source=old&&value===old.output?old.source:value;
   const output=uiLanguage==='en'?translateUI(source):source;records[attr]={source,output};if(value!==output)element.setAttribute(attr,output);
  }originalAttributes.set(element,records);
 }
 document.documentElement.lang=uiLanguage==='en'?'en':'zh-CN';document.title=uiLanguage==='en'?'Reference Studio · Character Reference Studio':'Reference Studio · 角色参考工作室';
 document.getElementById('languageSwitch').value=uiLanguage;
}
Object.assign(translations,{
 '双面显示':'Double-sided display',
 '双面显示可查看发片背面；关闭可检查面朝向，不会修复缺面或修改原模型。':'Double-sided display reveals hair-card backs. Turn it off to inspect face orientation; it does not repair missing faces or modify the source model.',
 '贴图生成中…':'Generating texture…',
 '重新生成白模':'Regenerate white model',
 '查看贴图结果':'View textured result',
 '确认白模并生成贴图':'Approve model → Generate texture',
 '已确认白模':'White model approved',
 '最终确认贴图模型':'Final approve textured model',
 '最终确认完成':'Final approval complete',
 '确认白模并生成贴图？':'Approve model and generate texture?',
 '确认后将提交付费纹理生成任务，无法撤回或取消已产生的 API 费用。此白模将锁定；系统会复制白模，在副本上生成贴图，原文件与历史版本仍会保留。':'This submits a paid texture task. Submission and incurred API charges cannot be reversed. This white model will be locked. Texturing uses an uploaded copy; the original and history are preserved.',
 '使用该部件的 Front / Left / Back / Right 四视图作为贴图参考。贴图目标：4K · 高清质量 · PBR。完成后需要再次检查并最终确认。':'Uses this component’s Front / Left / Back / Right references. Texture target: 4K · Detailed quality · PBR. Inspect the result and give final approval afterward.',
 '返回检查':'Back to review',
 '确认并开始生成贴图':'Confirm & generate texture',
 '贴图生成完成，请查看结果并最终确认。':'Texture ready. View the result and give final approval.',
 '贴图任务状态待核对，请查询原任务。':'Texture task status uncertain. Query the original task.',
 '贴图模型已最终确认，可下载或导出。':'Textured model approved. Download or export is available.',
 '先检查白模；确认后生成贴图，再进行最终确认。':'Review the white model, approve to generate texture, then give final approval.',
 '最终确认贴图后可下载或导出。':'Download or export after final texture approval.',
 '下载贴图模型':'Download textured model',
 '已提交新的白模候选，原模型保留。':'New white model candidate submitted. The original is preserved.',
 '贴图目标：4K · detailed · 实际分辨率待核对':'Texture target: 4K · detailed · Actual resolution not yet verified'
});
const uiObserver=new MutationObserver(()=>{uiObserver.disconnect();applyUILanguage();observeUI();});
function observeUI(){uiObserver.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['placeholder','aria-label','title','alt','data-hint']});}
document.getElementById('languageSwitch').onchange=event=>{uiLanguage=event.target.value;localStorage.setItem('studio-language',uiLanguage);uiObserver.disconnect();applyUILanguage();observeUI();};
applyUILanguage();observeUI();
