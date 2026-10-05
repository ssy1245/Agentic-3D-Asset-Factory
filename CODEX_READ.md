# Codex Read 项目接手指南

更新于 2026-10-05。本文件供新加入的 Codex 快速接手 Agentic 3D Asset Factory，覆盖当前软件、开发入口、实验素材、历史脚本与近期目标。用户当前指令优先于历史文档；本文件记录的是当前状态，不会自动授权付费生成或修改用户打开的 Blender 工程。

## 五分钟内建立项目认识

这是面向角色创作者的课程 Track 2 项目：帮助用户把语言中的角色想法转成更符合设计意图、可继续编辑的 3D 角色。二维设计、四视图与部件参考是中间表达。主要痛点是视觉问题难以具体化为修订要求、缺少明确的拆件流程、整体生成与参考不够一致，以及当前案例在 Blender 中呈现的贴图质量问题。

当前工作流是：文字或已有图 → 整体设计确认 → 整体四视图确认 → Head、Body & outfit、Hair 参考与检查 → 用户修订或确认 → 三部件白模 → 用户选择候选和按需贴图 → 原生 Blender 项目包 → 人工或有人监督的 Codex 组装及精修。

主要流程已有真实生成和导出案例。当前 Agentic 环节是部件图与批准的整体参考的双图检查，以及检查建议进入下一轮修订。整体四视图主动检查、最多 2–3 轮自主修订、独立可编辑的建议 prompt 展示仍是计划功能。不要把安装了 LangGraph 当作已经实现了自主循环。

当前近期目标是 **2026-10-09 presentation**。优先收敛能展示的检查与修订闭环、验证稳定性、准备完整流程与备用录像；无需扩大到通用建模、自动绑定或大规模生产平台。

建议阅读顺序：

1. [AGENTS.md](AGENTS.md)：必须保留的生成与资产约束。
2. 本文件：确定目录、代码入口和实际状态。
3. [README.md](README.md)：产品定位、Track 2 对应内容、工作流与实验陈述。
4. 根据任务进入下文代码或实验索引，不必先通读所有历史脚本。

## 先确定工作目录

**当前应用根目录**是 `/Users/shangyishen/Desktop/model_v2/Agent/Agentic-3D-Asset-Factory/`。以下启动和测试命令均在这个目录运行。这里有独立 `.git`，修改前检查本仓库的状态，保留用户和其他会话已有改动。

外层 `/Users/shangyishen/Desktop/model_v2/` 是实验工作区，包含早期同名 `asset_factory/`、旧计划和 Blender 修复脚本。外层 README 与 `docs/DEVELOPMENT.md` 描述旧的离线原型，不能用它们判断当前网页应用是否已接入 API。尤其不要在外层运行同名 Python 模块后误以为启动了当前应用。

文档发生冲突时，先核对用户最新说明与实际代码。当前应用行为以本目录代码为准；实验事实以对应原始记录为准，文件时间或历史截图不证明当前 Blender 内存状态。

## 当前功能与接手边界

| 环节 | 当前状态 | 主要入口 |
|---|---|---|
| 文字或图像设计、上传、反馈图、圈画 | 已实现 | `studio.py`、`provider.py`、`models.py`、`web/app.js` |
| 整体四视图生成与裁切 | 已实现；裁切启发式不验证朝向语义 | `views.py`、`prompts/turnaround.txt` |
| 三部件参考并行生成、历史版本和依赖失效 | 已实现 | `studio.py`、`storage.py` |
| 双图 Checker | 检查新生成的部件参考；不是 3D 网格质检 | `review.py`、`prompts/component_review.txt` |
| 检查建议参与修订 | 已实现；用户发起修订 | `studio.py` 中 `review_feedback` 与 prompt 构造 |
| 四视图自主检查和 2–3 轮修订 | 尚未实现 | 计划扩展 `review.py`、`studio.py`、`storage.py` 与前端 |
| 建议 prompt 的独立展示与编辑 | 尚未实现；当前建议在后端加入 prompt | `web/app.js` 与生成请求结构 |
| 三部件几何、候选选择、贴图 | 已实现；需要真实供应商配置 | `geometry.py`、`tripo.py` |
| 浏览器模型预览、原始拓扑元数据 | 已实现；原始 FBX 与 GLB 预览分开 | `model_preview.py`、`web/mesh-viewer.js` |
| 原生 `.blend` 和项目 ZIP 导出 | 已实现；后端需要 Blender | `blender_export.py`、`geometry.py` |
| 完整组装、精修、绑定与动作 | 下游 Blender/Codex 案例；应用不自动完成 | 外层实验和 Blender 工程 |

## 代码地图

下表路径相对于当前应用根目录；Python 模块位于 `src/asset_factory/`。

| 文件 | 负责内容与阅读重点 |
|---|---|
| `studio.py` | FastAPI 工厂 `create_app`、项目和图片接口、生成异步任务、检查触发、参考确认与重新打开、prompt 上下文、模型模块接入。先读 `project_memory`、`required_refs`、`invalidate`，再读 `execute`、`generate`、`approve`。 |
| `storage.py` | SQLite 项目与操作 JSON、请求唯一性、活动操作限制、重启恢复。数据库默认为 `data/studio.sqlite3`。 |
| `models.py` | 阶段、生成请求、选区与圈画数据校验。增加 prompt 编辑或循环设置时检查接口兼容。 |
| `provider.py` | OpenAI 图片生成和编辑、DemoProvider、图像归一化、圈画与蒙版、供应商结果未知的错误处理。 |
| `review.py` | 视觉检查请求与结构化输出：`verdict`、`summary`、按视角的问题、严重程度及建议。当前不自主重生成。 |
| `prompts.py` 与 `prompts/` | 设计、整体四视图、头、身体与服装、头发、通用规则、Checker 规则。修改拆件约束时同时检查生成与评估规则。 |
| `views.py` | 2×2 四视图布局和基于浅色背景空白带的裁切；不确定布局会报错，不能把成功裁切等同于四视图正确。 |
| `tripo.py` | 上传、几何请求、贴图、任务查询与下载；真实供应商参数及格式约束。 |
| `geometry.py` | 几何与材质操作状态、批量提交、候选批准、预览、单部件与完整项目导出。 |
| `model_preview.py` | Blender 可执行文件发现与后台 FBX 转 GLB 预览。 |
| `blender_export.py` | 隔离后台进程构建可携带贴图的 `.blend`，缓存导出结果；不会编辑用户当前场景。 |
| `web/app.js` | 用户工作流、阶段确认、修订、圈画、版本选择和导出交互。 |
| `web/models.js`、`web/mesh-viewer.js` | 三维候选 UI 与模型预览。 |
| `web/index.html`、`web/style.css`、`web/i18n.js` | 页面结构、样式及语言文案。 |
| `__main__.py` | 本地服务启动入口；默认端口 8765。 |

关键状态关系：批准的整体参考约束部件；生成操作保留输入和 prompt 快照；上游修改使相关下游版本过期，但保留历史资产。当前检查结果必须匹配修订源版本和批准的整体参考，才能进入下一次修订。不要让新模型错误关联用户后来修改过的参考。

当前确认整体四视图会自动开始三部件参考生成，确认最后一个部件会自动开始三维生成。因此这些确认操作可能触发付费请求，不能在真实项目上当作无成本点击测试。

## 启动和配置

环境说明见 [ENVIRONMENT.md](ENVIRONMENT.md)。项目要求 Python 3.13+，当前 `.python-version` 为 3.13.15；使用 uv、Node/npm，后端原生导出还需要 Blender。

```bash
uv sync --locked
npm ci
uv run uvicorn --app-dir src asset_factory.studio:create_app --factory --host 127.0.0.1 --port 8765
```

访问 `http://127.0.0.1:8765`，只使用一个服务进程，不开启多个 worker。启动前检查是否已有服务，不要为修改文档重启用户正在使用的服务。

配置保存在本目录 `.env`，参考 `.env.example` 和 README。已有 `.env` 不要覆盖，不要打印或复制密钥到交接说明。当前代码的默认配置如下，账号权限和实际运行配置需另外核对：

| 配置 | 用途与当前代码默认值 |
|---|---|
| `OPENAI_API_KEY` | 图片与视觉检查的后端凭据；兼容 `ChatGPT_API_KEY`、`CHATGPT_API_KEY` |
| `OPENAI_IMAGE_MODEL` | 图片模型，默认 `gpt-image-2.5-sunburst` |
| `OPENAI_REVIEW_MODEL` | Checker 模型，默认 `gpt-5-mini` |
| `TRIPO_API_KEY` | 三维服务凭据；兼容 `Tripo_AI_API_KEY`、`TRIPO_AI_API_KEY` |
| `TRIPO_MODEL_VERSION` | 几何模型，默认 `P2-20260801` |
| `BLENDER_BINARY` | 后端 Blender 可执行文件；也有自动发现逻辑 |

DemoProvider 使用本地 `fixtures/`，不调用图片生成服务，也不执行真实 Checker。样例被 Git 忽略，干净克隆不保证带有这些输入。`data/` 存数据库、资产和运行记录，同样不随源码提交；不要清空它来“重置”用户项目。

## 脚本用途与执行方式

| 脚本 | 用途 | 执行注意 |
|---|---|---|
| `scripts/check_services.py` | 查询图片模型列表和 Tripo 余额 | Python 脚本；发起真实网络读取，不生成资产。 |
| `scripts/export_blend.py` | 根据 manifest 建立独立场景、打包贴图并保存 | Blender 后台脚本；正常由 `blender_export.py` 调用。会删除所在场景对象，只能在隔离进程使用。 |
| `scripts/prepare_model_preview.py` | 读取原 FBX 面结构并导出 GLB 预览 | Blender 后台脚本；会重置场景，由预览模块调用。 |
| `scripts/import_blender.py` | 旧兼容包的 manifest 导入 | 在 Blender 中运行；会添加对象并保存新 `.blend`，不是当前网页项目 ZIP 的必要步骤。不要直接在用户正在编辑的场景中执行。 |
| `scripts/live_smoke.py` | 本机早期单次真实图片请求实验 | 本地未跟踪脚本，可能产生付费调用，不是常规测试入口。 |
| `scripts/split_grid_test.py` | 固定本地图片的裁切实验 | 本地未跟踪脚本；依赖特定 `data/` 路径，不是生产裁切实现。 |

源代码中没有 `live_tripo_smoke.py`；忽略规则里出现的文件名不能证明文件存在。优先使用实际应用模块和测试，不要把一次性脚本变成默认启动入口。

## 测试和稳定性验证

2026-10-05，本次接手整理使用现有 `.venv/bin/python -m pytest -q` 验证：**45 passed，7.22 秒**。它验证软件行为，不证明所有真实 API、资产质量或现场 demo 都稳定。README 中较早的测试记录保留其原始日期。

常规命令：

```bash
uv run pytest -q
uv run ruff check src tests
```

如果受限环境阻止 uv 访问缓存，而本地 `.venv` 已完整安装，可先使用 `.venv/bin/python -m pytest -q`；不要为了运行测试重装或覆盖用户环境。

`tests/test_studio.py` 主要覆盖阶段依赖、重复请求、重启与未知状态、上传和圈画、部件并发、Checker 失败保留图片、建议与用户反馈合并、Tripo 请求契约、四边形和四视图输入、候选与贴图关系、预览和导出。供应商主要使用 fake/mock；文件中带历史命名的测试不应单独替代当前实现判断。

`tests/test_blender_import.py` 检查旧导入脚本的包路径解析，不是在真实 Blender 中完成动画或贴图验收。新增自主循环应增加停止条件、次数上限、版本关联、中断恢复及人工接管的测试，避免只测试 prompt 中是否包含某个字符串。

presentation 前的稳定性重点是：完整操作能走到导出；刷新与重复点击不重复付费；失败及未知状态有清楚的恢复路径；上游改动不会混用旧模型与新参考；原生 `.blend` 可打开且贴图可携带；Checker 或 Blender 缺失时已有成果仍保留。真实生成测试按用户授权范围进行，不为证明稳定性反复购买同一任务。

## 实验素材和历史 Codex 工作

| 位置 | 内容及用途 |
|---|---|
| 本目录 `docs/JINX_EXPERIMENT.md` | Jinx 分件、组装、整体生成对照、后处理及展示顺序。 |
| 本目录 `Readme_PIC/JINX/` | Jinx 设计、参考、原始交付、组装和 baseline 截图；`postprocess/` 有修复图片与 JSON。 |
| 外层 `docs/EXPERIMENTS.md` | 白发角色 E01–E08，包含原始组装对照、几何统计与精修/动画历史。 |
| 外层 `reference2.png` | 白发双马尾角色参考。 |
| 外层 `2D-girl report/2D-girl.blend` | 用户确认仅组装、未作其他调整的对照工程。 |
| 外层 `2D-girl report/mesh_comparison.json` | 原始组装版本的网格统计。 |
| 外层 `v2_soft_anime_trial.blend` | 白发角色精修、绑定、舞台和动作案例；操作前核对当前打开文件及未保存状态。 |
| 外层 `docs/WHITE_HAIR_COMPARISON_INSPECT.json` | 较早精修场景检查，不能当作原始组装版的同一份统计。 |
| 外层 `docs/BLENDER_HANDOFF.md` | Blender 操作偏好、对象与动作历史。日期较早，其中“唯一保留工程”等目录状态已过时，需要重新核对。 |
| 外层 `material_repair/` | 背面串色、头发局部修复、检查与成本记录。 |
| 外层 `shader_work/` | 风格化材质、相机和接地检查/修改历史。 |
| 外层 `face_work/` | 表情、眨眼、局部动作修正及验证。 |
| 外层 `nail_work/` | 指甲生成、调整与跟随检查。 |
| 外层 `mmd_rebuild/` | 动作适配、稳定化与验证；历史脚本含特定骨架和坐标假设。 |
| 外层 `dance_audit/` | 舞蹈抽帧、图片汇总、检查数据与报告。 |
| 外层 `jinx_*.py` 与 `Jinx_report/` | Jinx 对齐、接口、肤色及辫子恢复的一次性操作和记录。 |
| 外层 `asset_factory/`、`tests/test_workflow.py`、`examples/demo_job.json` | 旧的离线任务记录原型；不是当前网页应用。 |
| 外层 `角色生成与装配计划_v1.6.md` | 旧路线，保留作历史资料；当前产品范围见应用 README。 |

历史 Blender 脚本通常依赖固定对象名、顶点编号、变换与帧号，部分带保存或场景重置操作。先检查脚本内容、适用对象与坐标空间，再决定是否复用；不要批量运行，也不要直接套到新角色上。操作用户当前 Blender 时通过 Computer Use 检查实际状态，保留用户已有修改，用户自行决定保存。应用的隔离后台资产导出与当前场景编辑是两种不同操作。

白发原始组装对照的已记录数据：整体生成为 50,374 个三角面；三部件合计为 56,869 个多边形，其中 45,613 个四边形，约占 80.2%；三角面等效数量为 102,482，约为整体生成的 2.03 倍。它支持在单次生成面数限制下累积几何容量和局部细节的案例结论，不直接证明总体质量、Checker 增益或同成本优势。

用户记录简单组装需 3–5 分钟；有人监督的 Codex 组装约 10 分钟，`gpt-6.1-sol` 消耗约 5% 的 Pro 5x 周使用额度。这里是用户估计的订阅额度记录，不是实际 token 数或软件 API 账单。发现 Codex 错误修改时及时停止并回退，避免后续操作叠加错误。

## 十月九日前的收敛任务

按用户目前方向，下一步优先明确 Agent 的判断和行动，随后验证演示稳定性。

1. **四视图有限自主修订**：对照批准的整体设计检查图像干净程度、完整性、朝向和一致性；支持最多 2–3 轮检查—修订，达到要求提前停止。初始生成不计入修订次数，达到上限或无法判断则交给用户。保留每轮依据、prompt 与版本，避免循环内自动批准参考或重复启动下游任务。
2. **拆件语义偏移的建议展示**：沿用已有整体/部件双图检查，定位身份、轮廓、配色、装饰和风格偏移；将建议转成用户可查看、编辑的 prompt，由用户决定是否执行。无需为展示 Agent 而自动替用户改变角色审美。
3. **稳定性与演示**：选择固定角色和可复现输入，展示一次真实检查与修订闭环，并覆盖项目导出。保留阶段结果，准备完整流程备用录像；区分现场运行与已有结果回放。

整体直接生成对照用于展示拆件策略；它不能单独证明 Checker 的增益。新增功能完成后同步更新 README、本文件、接口和测试，避免演示陈述领先于代码。Track 2 的报告、演示和代码交付要求以用户提供的 `/Users/shangyishen/Desktop/DASC7606C_Group_Project_0921.pdf` 为准。

## 不能漏掉的工程约束

- 所有生成请求保持 `quad=true`，不能静默退回三角网格。Head 目标 5,000 面，Body/Hair 各 20,000 面；先几何后材质。
- 标准三维输入必须是四张独立批准视图，顺序 front、left、back、right；不能只用正面或把四宫格直接当作四视图上传。
- 原始 FBX 是拓扑权威资产，GLB 是三角化浏览器预览。保留原始文件和生成历史。
- 头部在颈干处结束，不包含肩部扩展；身体保留肩部和短颈干连接余量，不生成重复完整脖子。规则详见 AGENTS 与部件 prompts。
- 中断或超时结果未知时先查询或人工核对原供应商任务，不能直接重复提交。当前开发模式没有统一调用预算上限，新增循环必须显式限制次数。
- 不提交 `.env`、数据库、生成资产、未获授权样例或带密钥的日志。不要清理用户的历史资源或自动保存其当前 Blender 工程。

## 文档维护和新会话入口

目前本目录实际存在的文档是 README、AGENTS、ENVIRONMENT、本文件以及 `docs/JINX_EXPERIMENT.md`。过去 README 引用的 `docs/PROJECT_REPORT.md`、`docs/REFERENCE_STUDIO.md`、`docs/ARCHITECTURE.md` 在本目录尚不存在，不应当作已经完成的报告或架构材料。

新会话可以这样开始：

> 请先阅读当前应用目录的 AGENTS.md、CODEX_READ.md 和 README.md，确认实际代码状态后接手。当前目标是十月九日 presentation 的 demo 收敛：加强四视图有限自主检查与修订、展示拆件语义偏移的可编辑建议 prompt，并验证稳定性。保留已有项目、资产和用户修改，先核对原任务再恢复未知请求，修改后运行相关测试并同步文档。
