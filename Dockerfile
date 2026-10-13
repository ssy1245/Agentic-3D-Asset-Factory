# 阶段 1：只安装浏览器需要的依赖，最终镜像不包含 Node。
FROM node:22-bookworm-slim AS web-deps
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund

# 阶段 2：Python + Linux Blender 应用镜像。
# 当前 Blender 安装包为 x64；在 Apple Silicon 上构建时指定 --platform linux/amd64。
FROM python:3.13-slim-bookworm AS runtime
WORKDIR /app

ARG TARGETARCH
RUN test "$TARGETARCH" = "amd64" || \
    (echo "此镜像使用 Linux x64 Blender，请指定 --platform linux/amd64" >&2; exit 1)

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    BLENDER_BINARY=/opt/blender/blender \
    PATH="/app/.venv/bin:/opt/blender:$PATH" \
    HOME=/home/app

# 安装 Blender 的系统库，以及下载和解压工具。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        xz-utils \
        libgl1 \
        libegl1 \
        libx11-6 \
        libxext6 \
        libxi6 \
        libxfixes3 \
        libxrender1 \
        libxxf86vm1 \
        libxrandr2 \
        libxkbcommon0 \
        libsm6 \
        libice6 \
        libglib2.0-0 \
        libdbus-1-3 \
        libwayland-client0 \
        libwayland-cursor0 \
        libwayland-egl1 \
        libfontconfig1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 下载官方 Linux Blender，并校验对应安装包的 SHA256。
ARG BLENDER_VERSION=5.2.2
RUN set -eux; \
    cd /tmp; \
    archive="blender-${BLENDER_VERSION}-linux-x64.tar.xz"; \
    base_url="https://download.blender.org/release/Blender5.2"; \
    curl -fSL --retry 3 --connect-timeout 30 \
        "$base_url/$archive" -o "$archive"; \
    curl -fSL --retry 3 --connect-timeout 30 \
        "$base_url/blender-${BLENDER_VERSION}.sha256" -o blender.sha256; \
    awk -v archive="$archive" '$2 == archive || $2 == "*" archive {print}' \
        blender.sha256 > blender-linux.sha256; \
    test -s blender-linux.sha256; \
    sha256sum -c blender-linux.sha256; \
    mkdir -p /opt/blender; \
    tar -xJf "$archive" -C /opt/blender --strip-components=1; \
    rm "$archive" blender.sha256 blender-linux.sha256; \
    /opt/blender/blender --version

# 根据锁文件安装 Python 运行依赖，不复制本机虚拟环境。
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /usr/local/bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-cache

# 只复制运行所需代码、prompt 和 Blender 脚本；不使用 COPY . .。
COPY --from=web-deps /web/node_modules /app/node_modules
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY scripts/prepare_model_preview.py scripts/export_blend.py scripts/import_blender.py ./scripts/

# 使用普通用户运行应用；data 在部署时挂载持久卷。
# fixtures 默认为空，需要本地演示素材时另行只读挂载。
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --home-dir /home/app app \
    && install -d -o app -g app /app/data /app/fixtures
USER 10001:10001

# 检查 Blender 在后台可启动，不加载或修改任何模型。
RUN /opt/blender/blender --background --factory-startup --disable-autoexec \
    --python-exit-code 1 --python-expr "print('BLENDER_BACKGROUND_STARTUP_OK')"

# EXPOSE 仅说明容器监听端口，不会自动向公网发布。
EXPOSE 8765

# 单进程启动；0.0.0.0 让反向代理能够访问容器内的服务。
CMD ["uvicorn", "--app-dir", "src", "asset_factory.studio:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]
