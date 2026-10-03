# Python 与 uv 环境

本项目使用 uv 管理 Python、依赖与项目独立的 `.venv`，当前固定 Python 3.13.15。`uv.lock` 应提交到 Git，用于复现依赖。

```bash
uv sync --locked
uv run python --version
uv run python your_script.py
uv run pytest
uv run ruff check .
```

通常无需手动激活环境，`uv run` 会使用本项目 `.venv`。若希望终端直接使用环境：

```bash
source .venv/bin/activate
```

添加业务依赖：`uv add 包名`。添加开发工具：`uv add --dev 包名`。

当前业务依赖：

- `httpx`：请求生成服务等 HTTP API。
- `pydantic`：校验任务和接口数据。
- `python-dotenv`：按需加载本地 `.env`，需要代码显式调用。
- `langchain`、`langgraph`：已加入依赖；首版参考图模块暂不启用 agent 循环。
- `fastapi`、`uvicorn`、`python-multipart`：网页后端、运行服务和上传图片。
- `pillow`：图片校验、格式归一化与生成编辑蒙版。

开发依赖：`pytest` 用于测试；`ruff` 用于代码检查和格式化。OpenAI 图片接口使用 httpx 直接调用；Blender 插件尚未接入。

VS Code 已配置 `.venv/bin/python` 为默认解释器。如解释器未自动切换，在“Python: Select Interpreter”中选择当前项目 `.venv`。Python 扩展需由编辑器提供，此次没有安装编辑器扩展。

`.env` 和 `.venv` 已加入忽略规则。不要把 API 密钥写进代码、文档或提交到 Git。现有 `.env` 未改动；服务启动时读取配置，密钥不会返回前端。
