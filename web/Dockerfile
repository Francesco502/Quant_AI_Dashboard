# ============================================================
# Quant-AI Dashboard - 前端 Dockerfile (Next.js)
# 多阶段构建，减小最终镜像体积
# ============================================================

# ---------- Stage 1: 安装依赖 + 构建 ----------
FROM node:20-slim AS builder
WORKDIR /app

# 启用 yarn (corepack)
RUN corepack enable && corepack prepare yarn@stable --activate

# 配置 yarn 使用 node_modules 模式（非 PnP）
RUN echo 'nodeLinker: node-modules' > .yarnrc.yml

# 复制依赖声明
COPY package.json package-lock.json* ./

# 安装依赖
RUN yarn install && ls node_modules/next/package.json

# 复制应用代码
COPY . .

# 设置构建时环境变量
# Docker 部署通过 Nginx 反向代理，前端使用相对路径 /api 访问后端
# 本地开发时在 .env.local 中设置 NEXT_PUBLIC_API_URL=http://localhost:8685/api
ENV NEXT_PUBLIC_API_URL=/api
ENV NEXT_TELEMETRY_DISABLED=1

# 构建（v3 低配优化：output=export 静态导出，无需 Node 运行时）
RUN npx next build

# ---------- Stage 2: 生产运行（静态文件，使用 serve 轻量托管） ----------
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# 从 builder 拷贝静态导出目录（output: export 生成 out/）
COPY --from=builder /app/out ./out

# 使用 serve 轻量托管静态文件（比完整 Next 进程省内存）
RUN corepack enable && npm install -g serve

EXPOSE 8686

CMD ["serve", "-s", "out", "-l", "8686"]
