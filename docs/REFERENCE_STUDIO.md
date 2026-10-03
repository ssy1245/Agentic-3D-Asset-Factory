# Reference Studio：首个实现模块

本模块先把角色参考图流程做成可操作的软件。当前是本机网页前端，不要求用户安装 Blender。

## 实现结构

- `studio.py`：FastAPI 接口、步骤门槛、异步出图与确认流程。
- `provider.py`：OpenAI 图片生成／编辑适配，以及明确标注的本地样例回放。
- `storage.py`：SQLite 任务及操作记录；PNG 图片保存在任务目录。
- `models.py`：步骤、修改请求和框选区域的校验。
- `web/`：普通 HTML/CSS/JavaScript 前端，不需要 Node 构建。
- `fixtures/`：本地角色图，仅用于交互演示，不提交到 Git；全新检出如需样例回放，需自行提供 `design.png`、`turnaround.png`、`head.png`、`body.png`、`hair.png`。真实 API 出图不依赖这些样例。
- `tests/test_studio.py`：关键流程与图片接口契约测试。

业务编排目前是明确的状态流，不启用 LangChain/LangGraph 的 agent 循环。模型负责生成／修改图像，程序负责版本、依赖、预算次数与记录，用户负责确认。之后需要 AI 质量判断和下一步路由时再接 agent。

## 依赖及状态

五个步骤严格依次确认后解锁，不可跳过。确认后自动进入下一步，已完成步骤可以返回。修改前一步会使所有后续版本失效并重新锁定。生成失败保留当前图；成功才创建新版本并使受影响的下游图过期。历史版本可查看，修改和批准只针对当前有效版本。

每个任务最多一个进行中或结果未知的操作。客户端给提交分配请求编号，服务端唯一约束保证相同编号只提交一次。提交响应在网络中丢失时，前端保留原提交，后续核对或重发使用原编号。服务端出图没有自动重试。

服务重启时，未开始的请求标记失败，正在调用的请求标记结果未知。未知结果需要用户核对供应商记录并填写说明后解除，解除不触发生成。已开始的失败或未知请求仍占用次数额度。

这是单进程、本地开发版本；后台任务尚未迁移到持久化队列，不支持跨进程并发执行。数据库与图片在 `data/`，不提交到 Git。密钥不进入网页、导出包或错误信息。

## 2026-10-03 验证

12 项自动测试通过：

1. 确认门槛、成功修改后的下游失效及重新生成。
2. 重复请求只调用一次，达到次数上限后拒绝新请求。
3. 未知失败保留旧图、阻止重试，人工核对不产生新调用。
4. 无效上传拒绝、五步骤上传确认、ZIP 清单和重启后数据保留。
5. 中断操作恢复为未知，不自动调用服务。
6. 编辑蒙版与首张参考尺寸一致，框内透明、框外不透明。
7. 模拟 OpenAI 接口：首次生成、多个参考图编辑、蒙版及返回用量。
8. 模拟超时不自动重试，不向用户暴露供应商原始错误。

浏览器实际验证：创建演示角色、读取样例、框选区域、填写修改意见、保留 V1/V2、批准整体设计后读取四视图。此测试没有真实 AI 编辑或付费请求。

## 下一步实验

真实出图验证应使用一个限定调用次数的角色任务，依次记录：请求编号、提示词、参考版本、反馈区域、返回用量、耗时和人工判断。优先测整体图到四视图的一致性，以及一次局部修改能否保留无关设计，再决定是否自动生成三个分件。

人工判断至少包括角色身份、视角齐全、服装前后对应、分件遮挡和皮肤／布料边界。内容质量未经验证前，不把流程控制的测试通过称为“稳定生成”。

接口依据：[OpenAI 图片生成指南](https://developers.openai.com/api/docs/guides/image-generation)、[图片编辑接口](https://developers.openai.com/api/reference/resources/images/methods/edit)。局部蒙版用于引导，仍可能影响未选区域。

## 整体设计双模式与图片反馈

整体设计提供文字生成和已有图像生成。文字生成不把当前版本或附件作为输入；图像生成以当前版本或上传的初始图为第一张输入。其余步骤继续使用已批准的上游参考。

修改意见可附带最多 3 张图片，作为输入末尾的细节参考；图片与文字、框选区域一同记录。上传图片经过格式、大小和归属校验，单独保存，不覆盖当前版本。输出版本和导出包记录附件编号，导出包包含输入参考图片。

新增测试：双模式输入约束、纯文字请求不夹带旧图、初始图与修改图的顺序、仅图片反馈提交、上传不创建输出版本、附件导出、跨角色图片拒绝及 3 张上限。测试使用模拟服务，不产生付费调用。

## 快速画笔圈画

默认工具为红色自由画笔，支持多笔、撤销和清除，也保留矩形框选。圈画针对当前有效输出版本；在整体设计上画笔操作会切换到已有图像生成并使用当前图。

前端以归一化坐标提交笔迹，后端基于原始分辨率绘制一张独立标注 PNG。模型输入顺序是原图、标注图、上游参考和附加修改图片；文字提示明确红线是位置说明，不是角色细节，输出不应保留标记。画笔本身不创建编辑蒙版，矩形框选仍用于蒙版。

新测试验证：原图不被改写、标注图正确绘制、图片顺序与文字提示、版本记录，以及缺少原图、超界坐标和过多笔迹时的拒绝。浏览器验证了圈画、撤销与文字共同提交；实际操作记录已保存标注图。使用本地演示，尚未验证真实模型对圈画的响应。

## API 接入与真实验证（2026-10-03）

兼容用户已有的 ChatGPT_API_KEY、Tripo_AI_API_KEY 变量名，OpenAI 与 Tripo 连接检查均成功。配置后新角色默认 OpenAI，已有 demo 任务不会偷偷切换为付费服务。

一次真实整体图生成通过软件后端完成并保存：角色任务 52117f78ab6e4d558336e3b22c6070b9，输出版本 8fd5c45d299840df93d2cab20d33e4d9。medium、1024×1536，约 15 秒，输入 token 100、输出 token 343。请求编号 req_f0a6cc738ae142eba594dc2bd87512d4，实际美元金额待账单确认。这不是跨视图或圈画修改效果测试。

Tripo 的 API 余额检查返回 0；没有提交真实三维生成。新模块 tripo.py / geometry.py 已接入部件参考裁切、图片上传、无材质几何提交、任务查询、GLB 下载与本地存储。测试通过模拟服务验证提交顺序、不重复创建、余额为零时不创建任务，以及下载时不向 CDN 转发密钥。

现共 16 项测试通过，新增五步骤严格顺序与重新锁定测试、三维流程／重复提交测试、零余额阻止任务测试和 Tripo HTTP 契约测试。

## 当前范围调整：先调图片（2026-10-03）

按用户要求，先不进入 3D。真实三维测试在提交前被中止，本地无三维任务记录。当前默认服务不加载 Tripo 适配、不查询余额、不注册三维路由，前端不显示三维面板。此前接口适配说明仅作为暂存工程记录。

将每步要求移到 prompts/ 下的文件，页面展示当前步骤规则，历史操作展示完整请求 prompt。使用 SHA256 的前 16 位标识通用约束与步骤要求的版本，操作及输出版本保存该标识和完整提示词。实际模型效果仍需逐步人工调试，不能从一次整体图成功推断其他步骤稳定。

调试顺序：整体图先核对身份、构图和比例；四视图核对前后服装对应与视角；头部核对去发后身份；身体核对服装与皮肤边界、手脚和遮挡；头发核对轮廓、发束连接与饰品。每次只改一类约束，保留前后版本，不自动连续调用付费服务。

新增默认关闭 3D 和提示词记录测试，总计 18 项通过。
# 角色项目记忆与上下文（2026-10-03）

一个角色对应一个 Project。图片和状态按项目隔离，项目接口及导出清单的 `memory` 提供最初角色描述、当前有效确认图和权威整体四视图。记忆从持久化的当前版本、确认和过期状态推导，避免重复保存权威指针造成不一致；历史图片不会自动成为权威参考。

整体四视图生成以确认后的整体设计图为输入。头部、身体与服装、头发生成以确认后的整体四视图为权威视觉输入，不再把不相关的先前部件作为视觉参考。五步顺序确认规则仍保留。修改部件时同时传入当前部件原图和权威整体四视图，圈画及修改参考另行标注用途。

每次生成的操作记录及输出版本保存 `context_snapshot`：项目 ID、角色描述、权威四视图版本和图片哈希、实际输入图片顺序与角色、提示词模板版本。完整提示词另行保存。部件模板统一为正面、左侧、背面、右侧四视图；身体沿用整体四视图的 T 字站姿。

整体四视图更新后，新图确认前不再提供有效权威参考，所有后续部件过期并停止继续生成；确认新四视图后生成的部件引用新版本。先前快照保留以便追溯。当前没有自动提取历史修改意见为长期文字设定，也没有宣称生成结果已经视觉一致；该质量仍需真实出图和人工确认。

验证：19 项测试通过，覆盖项目隔离、部件引用、修改上下文和权威参考换版。本次无付费生成，3D 仍暂停。

## 四视图裁切已接入工作台（2026-10-03）

非整体设计步骤统一请求 1024×1536 的 2×2 四宫格。布局规则由 `views.py` 提供，经 `prompts.py` 加入提示词及模板版本，页面规则预览与实际请求保持一致。生成或上传后自动检测浅色背景的空白带，拆分后按 front、left、back、right 保存方向标签；页面展示顺序为 Front、Back、Left、Right。裁图补成等尺寸画布，不独立缩放角色。

每张裁图记录原图版本、裁切框、填充偏移、图片哈希和部件标签。导出包通过 `views/部件/原图版本/朝向.png` 保留关系。历史版本可点击自动拆分，成功结果不会重复创建；原始图片保留用于圈画修改。新版本总是产生新的裁切结果，不覆盖旧图。

页面展示四卡片并支持点击放大、展开原图修改和统一确认。找不到空白带或有空视图时，显示待检查信息，前后端均阻止确认；这不是语义质量检查，朝向、肢体和角色一致性仍需人工确认。算法仅适用于有清楚空白带的浅色背景四宫格，不支持任意图片自动分割。旧图片不自动重排或重生成。

已将第二次真实出图测试结果以本地上传方式导入“白发角色 · 四视图裁切测试”，保留待确认状态，方便检查。此次软件集成未新增付费请求。20 项测试通过，并在网页验证四卡片和单图放大；所有运行图片与截图继续由 Git 忽略。

## 双语界面与等待状态（2026-10-03）

右上角提供中文 / English 切换，语言偏好保存在浏览器中。界面文字由 `web/i18n.js` 管理，包括步骤、按钮、表单、说明、动态状态和常见服务错误。角色名称、用户输入和实际发送的提示词快照保留原文；切换 UI 语言不改变项目内容。新增 UI 文案需要同步加入翻译表。

提交开始即显示加载遮罩和转圈；后台 queued/running 状态持续显示等待说明与已等待时间，重复提交按钮禁用。结果、失败或未知状态返回后收起遮罩；未知结果继续显示核对提示。界面不提供虚构百分比。

用独立端口的本地模拟服务验证中文及英文加载 UI、等待中语言切换、按钮禁用及成功后自动收起；正式工作台验证英文主界面、新建表单及刷新后的语言记忆。未为本次 UI 验证调用付费模型。模拟数据和证明截图均不提交 Git。

## 确认整体设计后自动生成四视图；开发阶段不限图片调用次数

整体设计按钮现在为“确认并生成四视图 / Approve & generate four views”。确认成功后自动进入第二步，将确认设计图与四宫格提示词提交一次；结果返回后自动拆分并停在人工确认。其他步骤的确认仍只推进下一步。自动请求编号绑定设计版本，重复请求通过服务端幂等记录复用；提交响应未知时保留原请求供核对，不自动重试。模拟网页验证只有一条四视图操作、参考图为确认设计版本、实际提示词包含布局规则、四个裁图生成成功。

开发阶段已移除图片生成次数上限，含旧项目；仍记录调用用量，保留单个进行中任务、未知结果核对和重复提交保护。创建表单不再显示次数上限。当前配置及项目读取的 max_calls 为 null，旧存储中的数值不再作为限制使用。20 项测试通过，软件验证本身无新增付费请求。

## 并行部件与自动视觉检查（2026-10-03）

确认整体四视图后自动调用 generate-components，头部、身体、头发并行生成，共用已确认的权威四视图。部件之间没有生成依赖；修改单个部件不会让其他部件过期。整体设计或整体四视图更新仍使所有部件过期。批次请求编号绑定四视图版本与部件，重复提交复用原操作，不自动重试失败任务。单项目最多三个不同部件同时生成，未知结果仍阻止新提交。

Head 只包含无发头部、耳朵和自然颈部，到脖子底部为止，不含肩、锁骨、胸和衣服。Body 保留肩和颈部底端接口，不附加第二段完整脖子。Hair 明确排除脸、眼鼻口、耳、头皮皮肤、脖子和人台头。三者共同参照整体四视图的切分层级与比例；图片约束不能保证最终网格无缝。

真实 API 生成每个部件后，自动通过 Responses API 做一次视觉检查，默认 OPENAI_REVIEW_MODEL=gpt-5-mini，可配置。检查提示词为 prompts/component_review.txt，使用组件图和权威整体四视图，输出结构化 summary、verdict、findings、suggested_change。页面显示检查结果，并允许把建议填入修改框。不会自动确认或重生成；检查失败和服务重启仍保留已生成图片，并转人工检查。每次正常部件生成增加一次模型检查调用，用量单独记录在质量报告中。

官方接口依据：[图片输入与模型能力](https://developers.openai.com/api/docs/models/gpt-5-mini)、[结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)。视觉检查仅看图片，不能证明拓扑、网格闭合或实际拼接质量。当前检查契约与并行流程经过模拟验证，尚未用真实生成的部件验证检查准确率。

23 项测试通过，覆盖真实并行执行（最大并发=3）、批次幂等、依赖与失效范围、检查失败保留图片、结构化检查输入。隔离网页模拟验证确认按钮自动启动三个任务并显示状态；本次实现与验证没有新增付费请求。


### Parallel workflow sidebar

The sidebar now shows three phases: overall design, whole-character four views, and a parallel component group. Head, body/outfit, and hair share one branch parent and have no sequential step numbers. Approving valid four views unlocks all three; each independently displays queued, generating, AI review, review concerns, awaiting approval, approved, failed, or outdated status. Approved component progress is displayed as 0–3 out of 3. The main component panel uses the same state resolver. Global request submission can temporarily disable navigation without changing branch status to locked. Chinese and English wording are supported, with a compact three-column branch layout on small screens.

Verification: JavaScript syntax checks, independent branch state/prerequisite checks, and visual inspection of the live studio sidebar. No paid generation was triggered for this UI change. Screenshot: `reference-studio-parallel-sidebar.jpg` (local, excluded from version control).


### Hair isolation: anatomical contours and shading

Updated the hair generation and visual-review instructions after a reference sheet retained visible ears and facial profiles despite mostly white face regions. Hair isolation now covers anatomy encoded in color, line work, shading, cast shadows and negative-space contours. Both profile views must remove recognisable nose/lips/chin and ear features. Hair genuinely occluded by removed anatomy may be reconstructed using surrounding strands and other views; genuine openings must remain, without filling the whole face region with hair. Normal curved hair shells and openings bounded by bangs are allowed. The reviewer flags observable anatomy and reports uncertainty when ambiguous.

These rules apply to newly submitted hair generations/edits and reviews. Historical image files and stored request prompts remain unchanged. Prompt changes alone do not establish generation quality; a new output needs visual inspection.


### Drag-and-drop change references

The shared change-reference upload area supports dragging one or multiple local PNG/JPEG/WebP images in every stage where change references are available. Click-to-browse remains available, with keyboard activation, a drag highlight and bilingual hints. Click and drop share the same attachment function, preview list and removal controls. Existing references count toward the three-image limit; unsupported formats and files exceeding 15 MiB are rejected before upload. Disabled/busy states prevent drops from bypassing upload restrictions. Dropping files outside the reference area does not navigate away from unsaved feedback. Uploading references alone does not trigger image generation.

Verification: JavaScript syntax checks; isolated no-network checks of the drop handler in all five stages, count/type/disabled guards and the click path; visual inspection in the live Hair page. No paid generation or additional live project attachments were submitted during verification. Screenshot: `reference-studio-drag-upload.jpg` (ignored).


### Bangs preservation during hair cleanup

Hair generation and review now require coherent fringe roots, continuous root-to-tip curves, gradual taper, and consistent projection of the same locks across views. Cleanup must preserve the approved fringe grouping, length, asymmetry and intentional wisps, without stretching hair along the former nose/cheek/chin or introducing scratch-like spikes. This supersedes the earlier broad instruction to eliminate recognisable face-shaped negative space: a natural face-sized opening bounded by real hair is allowed, and only observable anatomical features/tracing should trigger contamination findings. New requests read the updated prompt files; existing revisions remain unchanged. This is a prompt refinement, not evidence that future outputs will always meet the criteria.


### Head expression consistency

Head generation now treats the four views as one head at one instant, with the front expression as the anchor. Initial generation derives it from the approved whole-character front; edits preserve the current head front expression unless explicitly changed. Profiles must maintain the same jaw/lip opening, smile tension, teeth exposure and brow/eyelid expression, allowing perspective and occlusion rather than requiring identical 2D shapes. Visual review checks front-versus-profile mismatches, including open mouth versus closed/clenched teeth. Historical outputs are unchanged; new requests use the updated prompt.


### Regeneration combines visual-review feedback

Component edits automatically include the completed structure review of the current source revision when the report matches both that revision and the approved whole-character authority. The saved request context includes the review summary, findings and review prompt version alongside user feedback and original visual references. Suggestions are advisory; user changes take priority within the stage constraints, and uncertain findings must be checked against the images rather than blindly applied. A matching report with findings permits review-only regeneration with empty Changes; missing, failed, mismatched or empty reports do not. Regeneration is blocked while the source review is still running. The new output goes through the normal split and visual-review flow.

Verification: 28 tests passed, including combined user/review prompts, original source/authority inputs, immutable request snapshots, idempotent resubmission, review-only edits and rejection of mismatched/unavailable reports. JavaScript syntax and Python lint checks passed. Live UI shows the bilingual combination hint above Generate a revised version. No paid generation was submitted during verification.


### 3D result preview, confirmation and export

Added a component-stage model library and a GLB viewer using pinned @google/model-viewer 4.3.1, installed locally via `npm ci`. API geometry results can open a rotatable/zoomable preview, with front/back/side camera shortcuts, load/error states and basic GLB mesh/material counts. Each saved candidate has its own human inspection approval; approval and Blender export reject obsolete/unapproved source references. Approval records an inspection acknowledgment, not a topology guarantee. GLB download and Blender-package buttons unlock after approval in the UI. The raw download endpoint remains available for debugging existing outputs.

Blender export is a ZIP containing the selected GLB, provenance manifest, instructions and `import_blender.py`. Running that script inside Blender imports objects into a new named collection and saves a new `.blend` without overwriting an existing export. It preserves scene content and performs no automatic alignment, assembly or rigging. This export is not a native `.blend` until the script runs in Blender.

Local GLB preview supports a file up to 100 MiB entirely in the browser; it does not upload to the server or create a project candidate. This initial UI supports GLB, not arbitrary FBX/OBJ uploads. Paid Tripo generation remains disabled by default; viewing/export routes are available without vendor credentials. New batch generation and material generation are not implemented in this change.

Verification: 29 tests passed, including GLB preview/info, project isolation, inspection acknowledgment, approval-gated export, exported contents and rejection after upstream changes. Local tetrahedron GLB loaded successfully in the live browser and camera buttons worked, with no browser errors. No paid API generation was called. Blender package contents and script syntax were checked; the exported script was not executed inside Blender in this verification. Generated/test models, captures and node_modules remain excluded from Git.


### Phase 4: automatic parallel 3D submission

This supersedes the earlier paused-3D and manual-crop trial workflow. The default app now reads Tripo credentials from the backend environment. The sidebar has four phases. Head/body/hair remain parallel in phase 3; phase 4 unlocks only after all five current image references are approved and valid. The approval that completes all three components automatically submits one untextured geometry candidate per component and the UI switches to phase 4. The backend submits all three concurrently using the stored, tagged Front crops, with per-source stable request IDs. Task IDs, source crop IDs and progress are persisted. Duplicate approval/submission reuses existing requests; failed/unknown outcomes are not automatically retried.

Existing projects whose components were already approved before this update open phase 4 with an explicit initial submission button; loading or refreshing a project never creates paid jobs. Phase 4 shows individual queued/running/progress/failed/unknown/review states and a completed-model count. Completed models open the local GLB viewer and retain approval/export functionality. The current batch produces one candidate per part without textures; multi-candidate selection, automated mesh QA and later material generation remain future stages.

Verification: 30 tests passed, including true peak concurrency of three vendor mocks, all-component gating, automatic submission on the final out-of-order approval, exact Front input bytes, idempotency and preservation of geometry/export behavior. A separate local mock UI confirmed automatic navigation to phase 4, all three progress cards, completion at 3/3, GLB viewing and inspection approval unlocking export. Temporary test server/tab were closed. Real Tripo calls were not submitted by the verification.

### Quad geometry before materials

New geometry batches use `quad=true`, `smart_low_poly=false`, `texture=false`, `pbr=false` and `export_uv=false`. Head requests 5,000 faces; Body & outfit and Hair request 20,000 each. These are target limits, not verified exact counts or the vendor's maximum. Quad generation returns FBX; enabling smart low-poly with quads would cap the supported request at 10,000 faces ([official API documentation](https://platform.tripo3d.ai/docs/generation)). New batch request IDs distinguish this profile from older triangle jobs, while old results remain accessible.

Original FBX bytes remain the download/export source. A local Blender worker imports a separate copy, measures polygon types, and exports a derived GLB solely for the browser viewer. The Blender package importer now supports both FBX and legacy GLB. If Blender is unavailable or conversion fails, generation still succeeds and preserves the original. The UI provides an FBX inspection download, explicit acknowledgment of external Blender inspection, and a local preview retry without another vendor request. Configure `BLENDER_BINARY` when automatic discovery cannot find the executable.

Verification: 33 tests passed, including stage-specific quad request settings, signed FBX download without vendor authentication headers, missing-Blender fallback, preview retry, inspection approval and original FBX export. Python lint and JavaScript syntax checks passed. No paid geometry generation was submitted. Blender was not detected on this machine, so the actual Blender conversion/import execution and real generated mesh quality remain unverified.

### Separate 3D component pages and visible topology

Phase 4 now contains separate Head, Body & outfit and Hair inspection pages, with sidebar entries and tabs. Candidate cards are filtered by component; multiple saved candidates remain independently inspectable. No additional candidate-generation calls are introduced. Earlier GLB triangle results are labeled as earlier settings rather than quad outputs.

A local inspector based on pinned Three.js 0.183.2 replaces the basic preview display. It fits models to the camera, uses a dark background and directional lighting, and retains orbit/zoom and camera presets. Default white-model mode has an independent **Show topology edges** switch that overlays front-visible GLB triangle edges without hiding the solid shape. Original-material and X-ray wire modes are available; X-ray exposes hidden mesh edges, not a rig or skeleton. Display materials are temporary and exports retain original files. Model changes release renderer geometry/material resources and stale asynchronous loads are discarded.

Verification: existing 33 backend tests and Python lint passed; JavaScript syntax checks passed. Live browser verification used the existing generated Head GLB for model loading and the topology toggle, then checked component-specific navigation. No paid generation or inspection approval was submitted. Original FBX quad edges still require Blender inspection; the GLB viewer does not reconstruct quads.

### Candidate thumbnail gallery

Each geometry candidate now has a clickable thumbnail rendered from its actual saved GLB (including derived FBX previews), with the same dark background and white-model lighting as the detailed inspector. Clicking the image opens the existing rotate/zoom/topology dialog. Unavailable FBX previews and pending jobs show explicit placeholders rather than reference images presented as generated models.

The thumbnail is rendered once and cached in browser memory (up to 48 images). Temporary WebGL viewers are disposed after capture; polling reuses the image instead of running continuous render loops per card. No generation API or paid request is used. Live verification confirmed actual Head and Body thumbnails and clicking the Body image opened the matching detailed model. JavaScript syntax checks passed. Screenshot `reference-studio-model-thumbnails.jpg` is excluded from version control.

### Corrected four-view model inputs

Audit found that the first real geometry operations for Head, Body and Hair recorded `source_view=front` and were submitted as `image_to_model`. They did not use the other three approved component views. This supersedes earlier single-Front implementation descriptions: new normal generation uses `multiview_to_model` with four separately uploaded images in vendor order front, left, back, right. This differs from the UI quadrant order front, back, left, right. Each operation records input_mode and ordered input_views with independent immutable PNG snapshots and source IDs. All four crops are required. Uploads are sequential within each part, with three components still concurrent. Quad, face limits and untextured settings remain in place. Explicit manual-crop trials remain single-image requests.

New stable batch IDs prevent accidentally reusing older single-view jobs. Existing files remain visible, labeled as single-view inputs. No existing project load creates paid requests; only subsequent explicit generation or the normal final-component approval triggers submission. 34 tests pass, including exact multiview payload ordering and saved crop bytes. No new paid generation was submitted; cross-view reconstruction quality remains unverified. Official contract: https://docs.tripo3d.ai/model-generation/multiview-to-model-v3-0-v3-1.html

Thumbnail and default inspection camera angles now show the current Tripo models from +X, matching the visually verified front of the existing Hair model. Local models may use another axis. Live mouse dragging was verified to freely orbit the model; scroll zoom and right-button pan remain available.

### Head ends before the shoulder transition

Head generation now ends on the neck shaft before it flares outward into the shoulder/clavicle region. All four views must preserve usable neck length and terminate at the same level without shoulder-root wedges, trapezius slopes, wing-like skin extensions, a flared pedestal or bust. Body owns the complete shoulder transition below this shared cut. The visual reviewer checks these boundary artifacts and compares neck-shaft width rather than demanding the authority's broader shoulder-transition width. This refinement applies to future generations and edits; existing images remain unchanged. Prompt instructions do not guarantee a seamless mesh join. No paid generation was submitted for this change.

Body additionally retains a modest upward neck-shaft segment above the shoulder transition for joining allowance. A small overlap at the neck is intentional, while a full duplicate neck, jaw/head remnants and invented bulky connectors are excluded. Review must not flag the short neck segment merely for being present. Final overlap and joining still require mesh-level alignment; reference images do not establish exact mating dimensions.

### Reopen after approval

Approved references remain accessible from the sidebar with an Approved button state and a Reopen for changes action. Reopening changes only the current revision's approval state; images, history and saved models remain intact, and no API generation is submitted. Downstream navigation pauses while the prerequisite is unapproved; actual new revisions use existing downstream invalidation rules. Running/unknown operations or running visual reviews block reopening. The current version can be approved again through the normal workflow; stable generation IDs retain idempotency for unchanged inputs.

36 tests passed, including approval → reopen → approve, unchanged image bytes and version history, preserved sibling approvals and no extra operations during the demo flow.

### Single animated approval/reopen action

The two approval/reopen buttons are now one button. After approval, it briefly shows Approved, then changes to Reopen for changes with a muted red background and dark red text. Clicking it invokes the existing reopen endpoint; the same control returns to approval mode. Polling does not restart the transition. Busy/current-version guards remain, and reduced-motion preference skips the animation. No generation request is triggered by the transition or reopening.

### Direct FBX browser preview and candidate-card layout

This supersedes the missing-Blender preview blocker. The preview route now serves the original FBX when a derived GLB is unavailable; the frontend loads it with Three.js FBXLoader. Thumbnail and inspector use the same format selection. Existing files are previewed locally without another vendor request, while exports still use the original FBX. Original polygon counts remain unmeasured without Blender, and the wireframe represents render triangles. The fallback test now verifies a 200 response with original FBX bytes, format header and preserved exports; 36 tests pass. Live Head and Body FBX results loaded successfully.

Candidate cards use a compact format/face-target badge, a short four-view input line and separate full-width view/download buttons, preventing long inline download text from overflowing narrow cards.

### Head quality audit — 2026-10-03

Read-only queries of the completed Tripo tasks confirmed the following; no generation or additional generation charge was initiated during the audit.

| Setting | Earlier Head | Current Head |
| --- | --- | --- |
| Task | `cb720983-e3f1-4a77-85ec-e104d08f0c60` | `793cfe5f-450d-4d10-964c-2e766f3705f7` |
| Input | Single image | Four separate images |
| Model | `v3.1-20260211` | `v3.1-20260211` |
| Face limit | 50,000 | 5,000 |
| Quad requested | Not present in vendor input | `true` |
| Geometry quality | `standard` | `standard` |
| Texture / PBR | Off | Off |
| Observed original mesh | 48,546 GLB render triangles | 4,722 quads + 18 triangles in original FBX |

The FBX polygon count above was measured directly from its binary `PolygonVertexIndex` arrays, before browser triangulation. It is an audit measurement for this file, not a new automated topology-check feature. A quad request did not yield an entirely quad-only mesh.

All four immutable input PNG snapshots match their approved source crops byte for byte. Local crop labels and submission code use front, left, back, right, matching the documented API list order. The source sheet is front/left on the top row and back/right on the bottom row. Vendor task input confirms four files, but historical upload tokens were not persisted locally, so token-to-source correspondence cannot be independently reconstructed from the operation alone.

The current Head has visibly shallow eye and mouth detail in the clay preview; its mouth remains open in the side view. The reference still contains an outward flare at the neck base despite the current prompt instruction. Four generated drawings are not evidence of geometrically consistent orthographic projections. These are input/output observations, not proof of a single root cause.

The earlier/current comparison changes input mode, reference revision, polygon budget and topology simultaneously. It cannot isolate a multiview error. A controlled next experiment should hold the approved four PNGs, quad output and 5,000-face target fixed, changing one setting at a time. `geometry_quality=detailed` is a possible separate test, not a guaranteed fix; the documented surcharge is 20 credits. Do not silently increase the face target, disable quad output or regenerate an existing task.

Parameter reference: https://docs.tripo3d.ai/model-generation/multiview-to-model-v3-0-v3-1.html
