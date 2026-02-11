# 项目优化方案文档

## 1. 项目现状与目标差距分析

本项目旨在打造一个个人量化分析与交易学习平台。经过对现有代码库的深入分析，我们明确了当前功能与用户目标之间的差距。

| 目标维度 | 用户需求 | 当前现状 | 差距/不足 |
| :--- | :--- | :--- | :--- |
| **资产分析** | 指定资产（股/基/金）风险与涨跌分析 | 已有基础风险指标（VaR, 回撤）；预测模块 (`forecasting.py`) 为随机噪声 Demo；资产类型主要支持股票。 | 1. 缺乏真实的预测模型。<br>2. 基金/黄金等非股票资产的支持需显性化。<br>3. 缺乏基于真实策略的未来趋势判断。 |
| **全市场选股** | A股/HK股全市场策略找股，手动交易 | 具备 `stocktradebyz` 选股适配器框架；具备基础指标计算。 | 1. 缺乏全市场股票列表的自动获取与维护机制。<br>2. 选股性能优化不足（全市场扫描需高效）。<br>3. 选股结果展示与手动交易计划的衔接需加强。 |
| **模拟交易** | 模拟账户验证策略，观察盈余 | 仅有 `paper_trading.py` 生成单次"建仓计划"，无持久化账户状态。 | **重大缺失**：无法连续记录持仓、资金变化和历史盈亏曲线。当前仅是"信号生成器"，而非"模拟账户"。 |
| **回测功能** | 执行策略回测 | `backtest.py` 提供简单的日线回测框架。 | 功能基本可用，但报告简陋，缺乏详细的交易记录分析和图表。 |
| **多用户支持** | 多用户独立配置策略与资产 | 使用 `user_state.json` 单文件存储配置；RBAC 仅有定义未完全落地。 | 数据存储架构不支持多用户数据隔离；配置管理需从文件迁移至数据库。 |
| **分析周期** | 日线级长期分析 | 核心逻辑基于日线 (`days` 参数)。 | 符合需求。 |
| **Docker 部署** | 在个人服务器上通过 Docker 部署，7x24 小时运行 | docker-compose.yml 已适配 Next.js + FastAPI 新架构。 | Nginx 反向代理已配置，HTTPS 需要按需启用。 |

---

## 2. 详细优化方案

### 2.1 架构层优化：数据存储与多用户基础

为了支持多用户和持久化模拟交易，必须从文件存储迁移至关系型数据库。

*   **数据库迁移 (SQLite -> PostgreSQL/SQLite)**:
    *   **现状**: 依赖 `data/user_state.json` 存储配置，部分数据未持久化。
    *   **方案**: 完善 `core/database.py`，建立以下核心表：
        *   `users`: 用户基础信息。
        *   `user_assets`: 用户关注的资产列表（替代 `user_state.json` 中的 assets）。
        *   `user_strategies`: 用户配置的策略参数。
        *   `accounts`: 模拟账户资金表 (user_id, balance, frozen, updated_at)。
        *   `positions`: 模拟账户持仓表 (account_id, ticker, shares, avg_cost)。
        *   `trade_history`: 模拟交易流水 (account_id, ticker, action, price, shares, time)。
        *   `equity_history`: 每日权益快照（account_id, date, equity, cash, position_value）。

### 2.2 核心功能模块升级

#### A. 全市场选股引擎 (Market Screener)
*   **目标**: 自动化扫描 5000+ 只股票。
*   **优化点**:
    1.  **基础数据池维护**: 新增定时任务 (`scheduler.py`)，每日更新 A股/港股 基础列表（代码、名称）存入 DB。
    2.  **分批扫描机制**: 避免一次性请求过多导致 API 限流或内存溢出。实现 `MarketScanner` 类，支持分批加载数据 -> 计算指标 -> 筛选 -> 输出结果。
    3.  **策略解耦**: 确保 `Selector.py` 仅包含逻辑判断，指标计算复用 `technical_indicators.py`，避免代码冗余。

#### B. 持久化模拟交易系统 (Stateful Paper Trading)
*   **目标**: 真实的"模拟炒股"体验。
*   **优化点**:
    1.  **账户类重构**: 废弃无状态的 `SimulatedTrade`，实现 `PaperAccount` 类。
        *   支持 `buy(ticker, shares, price)`: 扣减 Cash，增加 Position，记录 Trade。
        *   支持 `sell(ticker, shares, price)`: 增加 Cash，扣减 Position，计算 Realized P&L。
        *   支持 `daily_settlement()`: 每日收盘后更新持仓市值，记录权益曲线。
    2.  **自动/手动模式**:
        *   **手动模式**: 在网页端点击"买入/卖出"按钮，调用后端 API 操作模拟账户。
        *   **量化托管模式**: 绑定策略，当策略触发信号时，自动执行模拟下单。

#### C. 资产分析与预测增强
*   **目标**: 提供有价值的未来趋势参考。
*   **优化点**:
    1.  **接入真实预测模型**: 改造 `forecasting.py`。
        *   **初级**: 集成 `Prophet` 或 `ARIMA` 进行时间序列趋势预测。
        *   **进阶**: 引入机器学习模型 (如 XGBoost/LSTM)，使用历史量价作为 Feature 训练模型。
    2.  **多资产类型适配**:
        *   在 `data_service.py` 中增加资产类型标签 (Stock/Fund/Gold)。
        *   针对基金（ETF/LOF）和黄金（通过 ETF 或 现货代码）进行专门的数据源适配（如 AkShare 的基金接口）。

#### D. Docker 生产化部署
*   **目标**: 在个人服务器上通过 Docker Compose 一键部署，实现 7x24 小时稳定运行。
*   **方案**:
    1.  **多容器编排**: 拆分为 4 个服务：
        *   `backend`: FastAPI 后端 API 服务 (uvicorn, port 8685)
        *   `frontend`: Next.js 前端 (standalone 模式, port 8686)
        *   `daemon`: 后台守护进程（数据更新、定时任务、日终结算）
        *   `nginx`: 反向代理，统一 HTTP/HTTPS 入口 (port 80/443)
    2.  **Nginx 反向代理规则**:
        *   `/` → 转发到 frontend:8686
        *   `/api` → 转发到 backend:8685
        *   `/ws` → WebSocket 转发到 backend:8685
    3.  **数据持久化**: Docker Volume 挂载 `data/`、`logs/`、SQLite DB 文件。
    4.  **镜像优化**: 后端使用 `python:3.11-slim`，前端使用多阶段构建（build → standalone）。
    5.  **安全配置**: CORS 动态配置、JWT 密钥通过环境变量注入、Nginx HTTPS 终止。

### 2.3 代码去冗余与规范化

1.  **指标计算统一**:
    *   检查 `core/stocktradebyz/Selector.py` 和 `core/technical_indicators.py`，将通用的 KDJ, MACD, MA 等计算逻辑全部收敛到 `technical_indicators.py`。
2.  **统一数据获取出口**:
    *   确保所有模块（包括回测、选股、分析）都调用 `core.data_service.load_price_data`，禁止在业务逻辑中直接调用 `akshare`，以便统一管理缓存和数据源切换。

---

## 3. 实施路线图 (Roadmap)

### 第一阶段：基础设施夯实 (Foundation)
- [x] **DB 初始化**: 完善 `core/database.py`，创建 Users, Accounts, Positions, equity_history 表。
- [x] **数据服务增强**: 升级 `data_service.py`，支持 Fund/Gold 代码识别与获取。
- [x] **指标库统一**: 清理 `Selector.py` 中的重复指标代码。

### 第二阶段：核心业务落地 (Core Features)
- [x] **模拟账户后端**: 实现 `PaperAccount` 类及其持久化逻辑 (CRUD)。
- [x] **模拟交易 UI**: 在前端 `Trading` 页面增加"我的持仓"、"交易历史"面板，对接后端 API。
- [x] **全市场扫描器**: 开发 `MarketScanner`，并在后端增加扫描接口。
- [x] **模拟交易日终结算**: 实现 `daily_settlement()` 方法，记录每日权益曲线。daemon 15:30 自动执行。

### 第三阶段：智能化与多用户 (Advanced)
- [x] **预测模型实装**: 集成 Prophet/ARIMA/XGBoost/LSTM/LightGBM/GRU 等多模型预测。
- [x] **JWT 鉴权**: 实现 JWT Token 认证，后端完整支持用户创建与登录。
- [x] **前端用户注册**: 注册页面 `/register`，对接后端 `POST /api/auth/register`。
- [x] **前端 Token 自动注入**: `fetchApi` 自动携带 Authorization Header，401 自动跳转登录。
- [ ] **多用户数据隔离**: 基于 `user_id` 隔离资产配置和模拟账户数据（当前硬编码 user_id=1）。

### 第四阶段：Docker 生产化部署 (Production Deployment)
- [x] **Docker 容器化**: docker-compose 编排 4 服务（backend + frontend + daemon + nginx）。
- [x] **Nginx 反向代理**: 统一入口，前端 `/`，API `/api`，WebSocket `/ws`。
- [x] **数据持久化**: Docker Volume 挂载 data/、logs/、models/ 等。
- [x] **环境变量管理**: `.env` 管理 SECRET_KEY、CORS_ORIGINS、API Token 等。
- [x] **健康检查与自动重启**: 所有服务配置 healthcheck + `restart: unless-stopped`。
- [x] **镜像优化**: 后端 python:3.11-slim，前端多阶段构建 standalone。
- [ ] **HTTPS 配置**: Nginx HTTPS 块已预置，需按域名配置证书。
- [ ] **CI/CD 流水线**: （可选）GitHub Actions 自动构建和推送镜像。

---

## 4. 结论

当前项目已完成从 Streamlit 单体架构到 **Next.js 前端 + FastAPI 后端** 的前后端分离重构，核心功能模块实现度达到约 **95%**。仅剩以下低优先级任务：

1. **多用户数据隔离**（将 `user_id=1` 硬编码替换为从 JWT Token 中提取用户 ID）
2. **HTTPS 证书配置**（Nginx 配置已预置，需要域名和 Let's Encrypt 证书）
3. **CI/CD 自动化**（可选）

项目已具备在个人服务器上通过 `docker compose up -d` 一键部署的能力。
