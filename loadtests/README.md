# 无真实 API 压测准备

这套配置专用于压测：Mock 图片、Checker、Tripo 上传/余额/任务/模型下载及贴图；不读取真实供应商 Key、不调用外部供应商、不启动 Blender 转换和原生导出。页面显示压测标记，`/load-test/status` 返回 `load_test=true`、`external_api_calls=false`。

## 启动独立环境

在项目根目录执行以下命令。只使用这份独立配置，不和正式 `compose.yaml` 合并：

```bash
docker compose -p asset-factory-loadtest -f compose.loadtest.yaml up -d --build
docker compose -p asset-factory-loadtest -f compose.loadtest.yaml ps
```

访问 http://127.0.0.1:8767 。测试注册通行证为 `load-test-local-only`，仅用于这个本机测试环境。容器没有 env_file，只注入测试配置，后端网络设为 internal，禁用外部出站；一个只转发到该后端的 Caddy 入口提供本机 8767 访问（入口容器不含 Key）。正式应用仍在 8766。数据卷与正式账号/资产分离。直接运行 Python 的模式也使用独立的 `load-test-data/`；不要手工指定正式 data_dir。

`STUDIO_LOAD_TEST` 只接受 0/1，非法值启动失败，避免误以为已隔离。压测开关在启动时决定，增删配置需重建容器。压测模式强制替换注入的 provider，真实供应商入口另有拦截；不支持失败后回退真实 API。

默认模拟延迟 250ms、失败率 0。可以在启动命令前设置变量：

```bash
STUDIO_MOCK_DELAY_MS=1000 STUDIO_MOCK_FAILURE_RATE=0.05 docker compose -p asset-factory-loadtest -f compose.loadtest.yaml up -d --force-recreate
```

延迟用于模拟供应商等待，失败率用于模拟供应商故障，不等于 HTTP 状态码出现比例。3D 任务还会受应用现有轮询间隔影响。图片是缓存的 512×768 占位图，3D 是 6 个四边形的测试立方体（原始 ASCII FBX、派生 GLB）；仍保留 quad=true、Head 5000/Body/Hair 20000 的请求目标，但不声称 Mock 达到真实面数或材质质量。原生 Blender 导出返回 503，避免压测时触发重计算。若要测试真实 Blender 性能，请另用隔离有效资产，不能用 Mock 结果当真实验收。

## 未来运行 Locust

本次仅准备与验证，没有执行并发压测。以下命令会下载 Locust 并实际产生负载，应在准备好后自行运行：

```bash
uv run --no-sync --with 'locust>=2,<3' locust -f loadtests/locustfile.py --host http://127.0.0.1:8767 --web-host 127.0.0.1
```

打开 http://127.0.0.1:8089，先 1 用户、每秒新增 1 用户检查，再逐步升压。脚本开始前先检查 Mock 状态，再准备一个共享测试账号/会话，各模拟用户创建独立测试项目，避免反复登录碰到正常认证限流。默认账号 `loadtester`，测试密码 `load-test-password-123`；已改密码时通过 `LOADTEST_USERNAME`/`LOADTEST_PASSWORD` 设置测试凭据。注册限流保持有效，多机大量 worker 应先规划测试账号，不修改正式防护规则。

初始场景覆盖项目读取、Mock 图片提交及查询。`TASK / mock image completion` 单独统计从提交到完成的延迟与失败，避免只测 202 响应。查看 HTTP 与 TASK 各自分组：Locust 的总计混合了这两类事件，不能将总计 RPS 当成纯 HTTP RPS。完整四视图、三部件、3D 和贴图可通过页面/接口继续测试；当前 Locust 文件没有声称已覆盖这些端到端场景。目标状态不是明确 Mock 时，脚本停止且不会发业务负载。

记录用户数、成功 RPS、P95/P99、错误率、任务完成耗时、CPU/RAM/磁盘/带宽。Mock 不能证明真实供应商性能或质量；小占位输出也不能代表大 PDF/3D 文件的公网带宽。正式容量评估应将负载机与被测机分开；同机测试仅做初步诊断。

生成记录会持续占用测试数据卷；测试结束先停止，再按保留需求整理测试结果。不要删除正式数据卷，也不要直接清空原 data：

```bash
docker compose -p asset-factory-loadtest -f compose.loadtest.yaml stop
```

参考：[Locust 官方场景指南](https://docs.locust.io/en/stable/writing-a-locustfile.html)、[Docker 官方内部网络说明](https://docs.docker.com/reference/compose-file/networks/)。

2026-10-13 验证：74 项测试通过；独立 Docker Mock 镜像构建成功，本机反向代理入口与认证可用，后端没有供应商 Key 且外网连接被阻止。只做功能验证，未运行 Locust 并发压测。
