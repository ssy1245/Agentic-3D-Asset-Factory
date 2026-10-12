# 账号与项目归属

本版提供用户名注册、登录、退出和项目隔离。注册后自动登录，账号名称不区分大小写，允许 3–40 位英文字母、数字、下划线和短横线；密码为 12–128 个字符。

## 数据结构

- `users`：`id`、唯一 `username`、加盐 scrypt `password_hash`、`created_at`。
- `sessions`：随机登录令牌的 SHA-256 摘要 `token_hash`、`user_id`、`expires_at`。令牌本身仅通过 HttpOnly、SameSite=Strict Cookie 发送，有效期七天；退出立即撤销。
- `projects.owner_id`：新增独立列并建立索引，项目 JSON 同时保存该字段。新项目由服务端绑定当前用户，客户端不能指定所有者。
- `operations`：保持原结构，通过所属项目控制访问。

所有 `/api/` 接口（注册和登录除外）需要登录。带项目编号的接口统一核验归属，包括图片、生成操作、模型预览和导出。非本人项目统一返回 404；列表仅包含本人项目。读取响应禁止缓存。修改请求检查 Origin 和浏览器的跨站请求标志；本机脚本可使用无 Origin 的请求和会话 Cookie。

## 历史项目迁移

启动时自动增加表与所属用户列，不删除项目、图片、模型或操作记录。旧项目保持未分配，不会自动归属第一个注册账号。

先在网页注册账号，然后在仓库根目录用本机管理命令分配。请先备份 `data/`；命令只分配尚无所属用户的项目。

分配一个指定项目：

```sh
PYTHONPATH=src uv run python -m asset_factory.auth --username your_username --project-id PROJECT_ID
```

明确将所有未分配项目交给这个账号：

```sh
PYTHONPATH=src uv run python -m asset_factory.auth --username your_username --all-unowned
```

注册过程不会执行上述分配。已有用户归属不会被命令覆盖。

## 本机与部署

原启动命令不变，首次启动打开网页即可看到登录界面。正在运行的旧服务需要在合适时机重启才能加载新代码。

本机 HTTP 默认不使用 Secure Cookie。通过 HTTPS 部署时必须设置 `STUDIO_COOKIE_SECURE=1`；反向代理应正确传递协议信息，且仅信任受控代理，否则 Origin 检查会拒绝请求。

密码使用 scrypt（N=2^17、r=8、p=1），同时限制两次哈希计算。账号请求按来源 IP 限制每分钟十次，这是单进程演示级限制；公开部署仍需共享限流、防代理绕过及注册策略。目前未实现密码找回、邮箱验证或多因素登录，也未验证万人承载。现有进程内生成任务和单进程启动限制保持不变。

参考：[OWASP 密码存储](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)、[会话管理](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)。
