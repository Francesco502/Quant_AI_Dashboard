# API Base URL Dev/Prod 收敛 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让前端在“本地前后端分离运行”和“线上一体化 Docker 同域 `/api` 反代”两种形态下，都能以配置驱动方式稳定访问后端，并确保全站请求链路一致、可验收。

**Architecture:** 以 `NEXT_PUBLIC_API_URL` 为唯一入口：本地用绝对 URL（`http://127.0.0.1:8685/api`），线上用相对路径（`/api`）。前端通过统一的 `resolveApiBaseUrl()` + `fetchApi()` 解析/拼接 URL（含规范化），任何页面/Hook 禁止硬编码 origin 或 localhost。可选：本地通过 Next.js rewrites 将 `/api/*` 代理到后端以避免 CORS。

**Tech Stack:** Next.js App Router（web）、TypeScript、FastAPI（api）、Docker/nginx（部署）

---

### Task 1: 收敛前端 API 基址解析（配置驱动 + 规范化）

**Files:**
- Modify: `web/src/lib/api.ts`
- Test: `web` 前端构建与类型检查（`npm run lint`, `npm run build`）

- [ ] **Step 1: 读取现有 `web/src/lib/api.ts` 并定位基址逻辑**
- [ ] **Step 2: 写/改 `resolveApiBaseUrl()`（或改造现有 `getEffectiveApiBaseUrl()`）**
  - 支持 `NEXT_PUBLIC_API_URL=/api`（相对）在浏览器端拼成 `${origin}/api`
  - 支持绝对 URL 原样使用
  - base 去尾随 `/`，endpoint 确保前导 `/`，避免双斜杠
- [ ] **Step 3: 让 `fetchApi()` 只使用该解析函数拼 URL**
- [ ] **Step 4: 在 `web` 下运行构建与 lint**
  - Run: `npm run lint`
  - Expected: 0 errors
  - Run: `npm run build`
  - Expected: build success

### Task 2: 全站请求链路一致（移除硬编码 origin/localhost）

**Files:**
- Modify: `web/src/lib/auth-context.tsx`
- Modify: `web/src/app/login/page.tsx`
- Modify: `web/src/app/register/page.tsx`
- Modify: `web/src/app/settings/page.tsx`
- Modify: `web/src/app/users/page.tsx`（若发现例外调用）
- Test: 手工验收路径（见 Task 6）

- [ ] **Step 1: 将 `auth-context.tsx` 的 `loadUser()` 改为调用 `fetchApi("/auth/me")`**
- [ ] **Step 2: 登录/注册页确保都用统一基址（不再直接引用 `API_BASE_URL` 常量或硬编码）**
- [ ] **Step 3: 设置页健康检查 URL 确保来自统一基址，并收敛错误提示到“线上用 `/api` + 反代”**
- [ ] **Step 4: 全仓验收检查（必须清零硬编码与启发式）**
  - 目标：除 `resolveApiBaseUrl()` 内“将相对 `/api` 拼到 `${window.location.origin}`”之外，仓库内不得出现任何手工拼接或启发式回退。
  - 必须清零的模式（全仓搜索确保 0 命中，或仅在允许位置出现）：
    - `window.location.origin`
    - `localhost:8685`
    - `127.0.0.1:8685`
    - 基于 hostname 的回退判断（例如 `location.hostname === "localhost"` 等）

### Task 3: 本地开发闭环（CORS 直连 vs rewrites 代理）

**Files:**
- Modify (optional): `web/next.config.js` 或 `web/next.config.mjs`（若项目已有则修改，否则创建）
- Modify: `DEPLOYMENT.md`
- Modify: `QUICKSTART.md`
- Modify (if exists): `env.example`

- [ ] **Step 1: 检查 `web` 是否已有 Next.js 配置文件**
- [ ] **Step 2: 若无，新增 `next.config` 并提供可选 rewrites（仅在本地启用）**
  - 目标：当 `NEXT_PUBLIC_API_URL=/api` 且 `NODE_ENV=development` 时，可将 `/api/:path*` 代理到 `http://127.0.0.1:8685/api/:path*`
  - 约束：生产环境不应把请求代理到 localhost
- [ ] **Step 3: 文档写明两种本地模式**
  - 模式 A：跨域直连（需要后端 `CORS_ORIGINS` 含 `8686`）
    - 细则：必须允许 `Authorization`/`Content-Type` 头，且允许 `OPTIONS` 预检，否则带 Bearer Token 的请求会被浏览器阻断
  - 模式 B：同源 `/api` + Next rewrites（推荐）
    - 边界：rewrites 只用于 Next dev server；生产部署仍依赖 nginx/网关反代

### Task 4: 部署文档与脚本同步（生产强约束）

**Files:**
- Modify: `DEPLOYMENT.md`
- Modify: `QUICKSTART.md`
- Modify (if relevant): `start.bat`, `start.ps1`, `docker-compose*.yml`, `nginx/*`

- [ ] **Step 1: 在部署文档中明确生产唯一正确配置**
  - `NEXT_PUBLIC_API_URL=/api`
  - `/api` 必须反代到后端容器（后端端口不对外）
- [ ] **Step 1.1: 生产验收条款（必须）**
  - 生产环境不得出现任何指向 `127.0.0.1`/`localhost` 的代理目标（无论是 rewrites 还是网关配置）
- [ ] **Step 2: 给出最小 nginx 反代示意片段（如仓库已有 nginx 配置则引用实际文件）**
- [ ] **Step 3: 本地启动脚本若会误导（默认写死 localhost），同步修正或输出提示**

### Task 5: 仓库卫生（EOL 统一，降低 Windows/CI diff 风险）

**Files:**
- Create: `.gitattributes`

- [ ] **Step 1: 新增 `.gitattributes` 固化关键文本文件的 eol（例如 `*.py text eol=lf`，`*.ts`/`*.tsx`/`*.md` 等）**
- [ ] **Step 2: 确认不会意外破坏 Windows 上脚本（`.bat`/`.ps1` 保持适合 Windows 的换行策略）**

### Task 6: 验收与回归（最小但覆盖关键链路）

**Files:**
- Test: `web` 构建与 lint
- Test: Python 编译与关键测试

- [ ] **Step 1: 前端**
  - 在仓库根目录（PowerShell）运行
  - Run: `cd web && npm run lint`
  - Run: `cd web && npm run build`
- [ ] **Step 2: 后端（基础）**
  - 在仓库根目录（PowerShell）运行
  - Run: `python -m compileall -q api core`
  - Expected: no errors
- [ ] **Step 3: 单测/冒烟（最小集）**
  - 在仓库根目录（PowerShell）运行
  - Run: `pytest tests/unit/test_api_response_cache.py -v`
  - Run: `pytest tests/test_v3_smoke.py -v`
- [ ] **Step 3.1: SSR/Server Component 约束（本阶段必须遵守）**
  - 禁止在 Server Component / SSR 路径调用 `fetchApi`（除非新增 `SITE_ORIGIN` 扩展任务）
  - 当前所有 API 调用必须发生在 `"use client"` 的组件/Hook 内
- [ ] **Step 4: 手工路径（说明性，不自动化）**
  - 本地模式 A：`NEXT_PUBLIC_API_URL=http://127.0.0.1:8685/api`，登录 -> `/settings` 健康在线 -> `/users`（admin）可用
  - 本地模式 B：`NEXT_PUBLIC_API_URL=/api` + rewrites，重复上述流程
  - 线上：`NEXT_PUBLIC_API_URL=/api` + 反代，确认 API 请求为同域 `/api/...` 而非用户 localhost

