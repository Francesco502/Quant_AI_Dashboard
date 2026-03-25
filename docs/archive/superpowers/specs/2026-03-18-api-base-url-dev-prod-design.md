## 背景与目标

当前项目同时存在两类运行形态：

- **本地开发/测试**：前端 Next.js 运行在 `8686`，后端 FastAPI 运行在 `8685`，二者分开启动。
- **线上一体化 Docker 部署**：用户**只访问前端端口**；后端端口不对外开放；前端通过**同域反代** `/<api-prefix>`（推荐 `/api`）访问后端。

本设计的目标是让“API 基址（base URL）”在两种形态下都**可预测、可配置、无启发式猜测**，并确保所有前端请求（登录/注册、鉴权 `/auth/me`、健康检查、业务接口、管理页）都走同一条规则，避免出现“部分页面可用、部分接口离线/401/404”的割裂。

非目标：

- 不引入新的部署拓扑（例如前后端分域名），仅保证未来可扩展。
- 不重构业务 API 结构（`/api/...` 路由保持现状）。

## 现状痛点（观察到的具体问题）

- 部署时 `NEXT_PUBLIC_API_URL` 若被设为 `http://127.0.0.1:8685/api`，用户从外部访问前端页面会导致健康检查等请求指向“用户自己的 localhost”，从而显示离线。
- 现有实现中存在“部分请求走 `getEffectiveApiBaseUrl()`，部分请求硬编码 `window.location.origin + /api`”的混用，容易导致鉴权/角色加载不一致，从而影响 UI（例如管理员入口展示）。
- 需要同时保留本地前后端分开跑的能力，方便开发与 e2e 测试。

## 设计方案（推荐：方案 A，配置驱动，无启发式）

核心原则：**用 `NEXT_PUBLIC_API_URL` 明确区分 dev/prod**。生产一体化部署统一设置为相对路径 `/api`，本地开发设置为绝对 URL `http://127.0.0.1:8685/api`。

### API 基址解析规则（唯一权威）

定义 `resolveApiBaseUrl()`（名称可沿用现有 `getEffectiveApiBaseUrl()`）。该规则是**唯一权威**，仓库内禁止出现任何硬编码拼接（例如 `window.location.origin + "/api"`、`http://127.0.0.1:8685/api`、或自行判断 hostname 回退）；所有 API 请求必须经由 `fetchApi()` 或调用 `resolveApiBaseUrl()` 取 base。

- 若 `typeof window === "undefined"`（SSR/构建期）：
  - 返回 `process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8685/api"`
  - 约束：**禁止在 Server Component / SSR 路径调用 `fetchApi`**（除非补齐 server-side origin 方案）。当前项目 API 调用应放在 `"use client"` 的组件/Hook 内执行。
  - 若未来确需 SSR 调用：新增 `SITE_ORIGIN`（后端/网关的对外 origin，例如 `https://example.com`），当 `NEXT_PUBLIC_API_URL` 为相对路径时，SSR 端用 `${SITE_ORIGIN}${NEXT_PUBLIC_API_URL}` 解析。
- 若在浏览器端：
  - 读取 `NEXT_PUBLIC_API_URL`（默认 `"http://127.0.0.1:8685/api"` 仅用于本地兜底）
  - 若该值以 `/` 开头（相对路径，例如 `/api`），则返回 `${window.location.origin}${value}`
  - 否则返回该值（绝对 URL）

#### 路径规范化（必须）

- `NEXT_PUBLIC_API_URL` 允许两类值：
  - 绝对：`http(s)://host[:port]/api`
  - 相对：`/api`
- `resolveApiBaseUrl()` 必须规范化 base（去除尾随 `/`），`fetchApi()` 必须规范化 endpoint（确保以 `/` 开头），并在拼接时避免双斜杠。

此方案不基于 hostname 做“localhost 回退”判断，从而避免误判；行为完全由配置决定。

### 前端调用链收敛

所有前端请求统一通过同一套工具函数：

- `fetchApi(endpoint, options)` 内部使用 `resolveApiBaseUrl()`
- 登录页、注册页、设置页健康检查、用户管理页、鉴权上下文 `loadUser()` 等所有直接 `fetch(...)` 的位置，必须改为使用 `fetchApi(...)`（优先）或至少调用 `resolveApiBaseUrl()` 取 base。
- 验收约束：仓库内不允许存在绕开统一基址规则的“例外请求”。

### 环境配置约定

#### 本地开发（前后端分离）

- 后端：`uvicorn api.main:app --reload --port 8685`
- 前端：二选一（必须形成闭环）
  - **选项 1：直接跨域访问后端（需要后端 CORS）**
    - `NEXT_PUBLIC_API_URL=http://127.0.0.1:8685/api`
    - 需要后端允许 `http://localhost:8686,http://127.0.0.1:8686`，并允许 `Authorization` 头与 `OPTIONS` 预检（带 Bearer Token 的请求会触发 preflight）。
  - **选项 2：本地也统一用同源 `/api`（推荐，避免 CORS）**
    - `NEXT_PUBLIC_API_URL=/api`
    - Next dev server 配置 rewrites（示意）：`/api/:path* -> http://127.0.0.1:8685/api/:path*`，浏览器侧不跨域。

#### 线上 Docker（一体化，同域反代）

- 反代规则：对外仅开放前端入口；`/api` 反代到后端容器（内部网络）
- 责任边界：反代必须在对外入口层实现（例如 nginx/caddy/traefik，或前端容器内置网关）。验收标准是：外部访问 `https://<site>/api/...` 能到达后端，且后端端口不直接暴露。
- 最小可复制示例（nginx 示意，仅用于说明）：
  - `location /api/ { proxy_pass http://backend:8685/api/; proxy_set_header Host $host; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }`
- 前端环境变量：**强约束**
  - `NEXT_PUBLIC_API_URL=/api`

### 用户可理解的错误提示

在设置页健康检查失败时，提示应明确且可执行：

- “一体化 Docker 部署：请确保反代已将 `/api` 转发到后端，并在前端容器设置 `NEXT_PUBLIC_API_URL=/api`。”

## 变更范围（预期修改文件）

- `web/src/lib/api.ts`：收敛并实现基址解析规则（相对路径拼接 origin；移除启发式回退或改为配置驱动）。
- `web/src/lib/auth-context.tsx`：`loadUser()` 改为走统一基址/`fetchApi("/auth/me")`，避免硬编码 origin。
- `web/src/app/login/page.tsx`、`web/src/app/register/page.tsx`：改为走统一基址（目前已部分完成）。
- `web/src/app/settings/page.tsx`：健康检查走统一基址，并收敛提示文案。
- `web/src/app/users/page.tsx`：已使用 `fetchApi`，确保其依赖的基址规则正确。
- 文档：`DEPLOYMENT.md` / `QUICKSTART.md` 增补“线上一体化部署必须配置 `NEXT_PUBLIC_API_URL=/api`”。
- 仓库卫生：新增 `.gitattributes`（可选，但强烈建议）统一 EOL，降低 Windows/CI diff 风险。
- 若仓库中存在：`.env.example`、`docker-compose.yml`、反代配置（nginx/caddy/traefik）、本地启动脚本（`start.bat`/`start.ps1`），需同步写明 dev/prod 的 `NEXT_PUBLIC_API_URL` 推荐值与反代要求，避免误配。

## 风险与缓解

- **风险：SSR 端若调用 `fetchApi` 且 base 为相对路径**会缺少 origin。
  - 缓解：当前强约束为“禁止 SSR 调用 `fetchApi`”；若未来必须 SSR 调用，引入 `SITE_ORIGIN` 并在 `resolveApiBaseUrl()` 中支持 server-side 拼接。
- **风险：线上未配置反代**会导致所有 API 失败。
  - 缓解：在健康检查与登录错误提示中明确指出 `/api` 反代要求和 `NEXT_PUBLIC_API_URL=/api` 配置。

## 测试计划（验收标准）

本地：

- 启动后端 `8685` 与前端 `8686`
- 若采用“跨域直连”模式：确认后端 CORS 允许 `8686`（含 `Authorization` 与 `OPTIONS` 预检），然后配置 `NEXT_PUBLIC_API_URL=http://127.0.0.1:8685/api`
- 若采用“同源 /api + rewrites”模式：配置 `NEXT_PUBLIC_API_URL=/api` 并启用 rewrites
- 验收：
  - 登录/注册成功
  - `Authorization: Bearer <token>` 的接口调用正常（无 preflight/CORS 阻断）
  - `/auth/me` 返回用户与角色，管理员用户可看到“用户管理”
  - token 无效/过期时，前端能引导回 `/login`（或给出清晰错误）

线上（模拟）：

- `NEXT_PUBLIC_API_URL=/api`
- 通过反代访问前端页面，健康检查指向同域 `/api/health` 并显示在线
- 管理员登录后显示“用户管理”，并能拉取 `/api/auth/users`（若后端实现存在）

