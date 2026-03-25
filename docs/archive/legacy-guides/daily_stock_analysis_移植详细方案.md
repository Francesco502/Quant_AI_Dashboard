# daily_stock_analysis 移植详细方案

> 依据 [docs/daily_stock_analysis_移植可行性评估.md](./daily_stock_analysis_移植可行性评估.md) 与参考项目 [ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis)，本方案给出**文件级**移植步骤、目录映射、API 规范、配置与验收标准，便于按阶段实施。
>
> **实现状态与完善建议**：当前仓库多数 Phase 1/2/3 项已实现，方案不足与进一步实施建议见 [daily_stock_analysis_移植完善建议.md](./daily_stock_analysis_移植完善建议.md)。

---

## 〇、实现状态速览（当前仓库）

| 模块 | 状态 | 说明 |
|------|------|------|
| core/llm_client、daily_analysis、market_review、notification、search_service | ✅ 已实现 | 入口与方案一致 |
| api/routers/llm_analysis、market | ✅ 已实现 | dashboard、run-daily、backtest、daily-review |
| web：dashboard-llm、market-review、ai-backtest | ✅ 已实现 | 可再补：追高/趋势提示、summary、附带复盘勾选 |
| daemon + scheduler + .github/workflows/daily-analysis.yml | ✅ 已实现 | 定时与手动触发 |
| 筹码接入 builder、extract-from-image、SerpAPI 等扩展 | ⏳ 可选 | 见完善建议文档 |

---

## 一、参考项目与本项目目录映射

### 1.1 daily_stock_analysis 关键文件（参考）

| 参考路径 | 职责 | 行数/规模 |
|----------|------|-----------|
| `main.py` | CLI 入口、每日分析流程、大盘复盘、推送调度 | ~25k 行 |
| `analyzer_service.py` | 分析服务封装，供 API/CLI 调用 | ~3.5k |
| `server.py` / `webui.py` | FastAPI 服务与 Web UI 挂载 | ~1k / ~1.2k |
| `src/analyzer.py` | 单股/多股 LLM 分析、prompt 拼装、解析 | ~66k |
| `src/stock_analyzer.py` | 单股数据汇总（行情+技术+筹码等） | ~31k |
| `src/market_analyzer.py` | 大盘复盘（指数、板块、涨跌家数） | ~27k |
| `src/notification.py` | 企微、飞书、Telegram、钉钉、邮件、Pushover | ~139k |
| `src/search_service.py` | Tavily/SerpAPI/Bocha/Brave 新闻搜索 | ~58k |
| `src/config.py` | 环境变量与配置项 | ~33k |
| `src/storage.py` | 自选股/设置持久化 | ~43k |
| `data_provider/` | 行情多源（AkShare/Tushare/YFinance 等） | 多文件 |

### 1.2 移植目标位置（Quant_AI_Dashboard）

| 本仓库路径 | 用途 | 参考来源 |
|------------|------|----------|
| `core/daily_analysis/`（新建） | 每日智能分析：LLM 决策、复盘、推送编排 | main.py + analyzer_service + src/analyzer + src/stock_analyzer |
| `core/llm_client.py`（新建） | LLM 统一调用（Gemini/OpenAI/DeepSeek/Claude/Ollama） | src/config + 各模型调用逻辑 |
| `core/market_review.py`（新建） | 大盘复盘（指数、板块、北向资金） | src/market_analyzer |
| `core/search_service.py`（新建） | 新闻/舆情搜索（Tavily/SerpAPI 等） | src/search_service |
| `core/notification/`（新建）或扩展 `core/monitoring/` | 决策/复盘推送（企微、飞书、钉钉等） | src/notification |
| `core/data_service.py`（扩展） | 筹码、北向资金接口（可选 Pytdx/Baostock） | data_provider + 现有 data_service |
| `core/technical_indicators.py`（扩展） | 乖离率、MA 排列（交易纪律用） | 现有 + 参考项目指标 |
| `api/routers/llm_analysis.py`（新建） | 决策仪表盘、图片识别等 API | server.py + API 路由 |
| `api/routers/market.py`（新建） | 大盘复盘 API | server.py |
| `web/src/app/dashboard-llm/page.tsx`（新建） | 决策仪表盘页 | 参考 dsa-web 对应页 |
| `web/src/app/market-review/page.tsx`（新建） | 大盘复盘页 | 参考 dsa-web |
| `web/src/app/ai-backtest/page.tsx`（Phase 3） | AI 回测结果页 | 新建 |
| `.github/workflows/daily-analysis.yml`（新建） | GitHub Actions 定时分析 | 参考 .github/workflows |

---

## 二、Phase 1 详细移植步骤

### 2.1 新增后端核心模块

#### 2.1.1 LLM 客户端 `core/llm_client.py`

- **职责**：根据 env 选择模型（Gemini / OpenAI 兼容 / DeepSeek / 通义 / Claude / Ollama），统一 `chat_completion(text, system_prompt?)` 接口。
- **参考**：daily_stock_analysis 的 `src/config.py` 中 AI 相关配置及各模型调用方式。
- **接口**：
  - `get_client() -> BaseLLMClient`（按 `OPENAI_API_KEY` / `GEMINI_API_KEY` 等优先级选择）
  - `chat_completion(messages: List[Dict], model: str | None) -> str`
- **依赖**：`openai`（OpenAI 兼容）、`google-generativeai`（Gemini，可选）。Ollama 为本地 HTTP。

#### 2.1.2 每日分析包 `core/daily_analysis/`

建议结构：

```
core/daily_analysis/
├── __init__.py
├── config.py      # 从 env 读取 LLM、推送、BIAS_THRESHOLD、自选列表等
├── builder.py     # 拼装单股输入：行情 + 技术面 + 筹码 + 舆情（Phase 2 加舆情）
├── prompts.py     # 决策仪表盘 system/user prompt 模板，含交易纪律说明
├── parser.py      # 解析 LLM 输出为结构化决策（结论、买入/止损/目标价、检查清单）
└── runner.py      # run_daily_analysis(tickers, market) -> 多股决策 + 可选复盘 + 推送
```

- **builder.py**：调用 `data_service.load_price_data`、`technical_indicators` 取 OHLCV 与 MA/乖离率等；Phase 1 筹码可先占位或简单 AkShare 接口；Phase 2 再接入 `search_service` 舆情。
- **prompts.py**：明确要求输出格式（如 JSON 或固定 Markdown 块），包含：一句话结论、买入价、止损价、目标价、检查清单（满足/注意/不满足）、追高与趋势提示（乖离率>5%、MA 排列）。
- **parser.py**：正则或 JSON 解析，输出统一结构（见 2.3 节数据模型）。
- **runner.py**：循环 tickers，对每只调用 builder → LLM → parser；汇总后可选调用 `market_review.daily_review()`；再调用 `notification` 发送。

#### 2.1.3 大盘复盘 `core/market_review.py`

- **职责**：拉取主要指数、涨跌家数、板块领涨领跌、**北向资金**；支持 `market=cn|us|both`。
- **参考**：`src/market_analyzer.py`。
- **接口**：
  - `daily_review(market: str = "cn") -> Dict`  
    返回结构见 2.3 节。
- **数据来源**：优先用现有 `data_service` 与 AkShare（如 `ak.stock_zh_a_spot_em`、`ak.stock_sector_spot`、北向资金接口）；美股用 yfinance 指数。

#### 2.1.4 推送扩展

- **方案 A**：在 `core/monitoring/alert_manager.py` 中增加 `WechatChannel`、`FeishuChannel`、`DingTalkChannel`、`PushoverChannel`，复用现有 `Alert` 与 `send` 流程；决策/复盘内容转为 `Alert.message` 或单独入口。
- **方案 B**（推荐）：新建 `core/notification/`，专门用于「决策报告 / 复盘报告」推送，格式与 daily_stock_analysis 一致（Markdown/卡片）；`daily_analysis.runner` 只调 `notification.send_report(type, content)`，与系统告警解耦。
- **参考**：`src/notification.py` 中各渠道的请求格式（Webhook URL、body 结构）。

### 2.2 Phase 1 新增/修改文件清单

| 操作 | 路径 |
|------|------|
| 新增 | `core/llm_client.py` |
| 新增 | `core/daily_analysis/__init__.py` |
| 新增 | `core/daily_analysis/config.py` |
| 新增 | `core/daily_analysis/builder.py` |
| 新增 | `core/daily_analysis/prompts.py` |
| 新增 | `core/daily_analysis/parser.py` |
| 新增 | `core/daily_analysis/runner.py` |
| 新增 | `core/market_review.py` |
| 新增 | `core/notification/__init__.py` |
| 新增 | `core/notification/channels.py`（企微、飞书、钉钉、邮件、Pushover、Telegram） |
| 新增 | `core/notification/formatter.py`（决策/复盘 Markdown 格式化） |
| 扩展 | `core/technical_indicators.py`（乖离率、MA 排列辅助） |
| 扩展 | `core/data_service.py`（北向资金、筹码接口，可选） |
| 新增 | `api/routers/llm_analysis.py` |
| 新增 | `api/routers/market.py` |
| 修改 | `api/main.py`（注册上述两个 router） |
| 修改 | `core/scheduler.py`（增加 `setup_daily_analysis_job`） |
| 修改 | `core/daemon.py`（可选：配置与调用每日分析任务） |
| 修改 | `requirements.txt`（openai、google-generativeai 等） |
| 修改 | `env.example`（见 2.4 节） |

### 2.3 Phase 1 数据模型与 API 规范

#### 决策仪表盘响应结构（单股）

```json
{
  "ticker": "600519",
  "name": "贵州茅台",
  "conclusion": "一句话核心结论",
  "action": "买入|观望|卖出",
  "score": 65,
  "bias_risk": "乖离率 6%，提示追高风险",
  "trend_ok": true,
  "buy_price": 1680.0,
  "stop_loss": 1620.0,
  "target_price": 1780.0,
  "checklist": [
    {"item": "MA5>MA10>MA20", "status": "满足"},
    {"item": "量能配合", "status": "注意"}
  ],
  "highlights": ["利好1", "利好2"],
  "risks": ["风险1", "风险2"]
}
```

#### 大盘复盘响应结构

```json
{
  "date": "2026-02-25",
  "market": "cn",
  "indices": [
    {"name": "上证指数", "value": 3250.12, "pct_change": 0.85},
    {"name": "深证成指", "value": 10521.36, "pct_change": 1.02}
  ],
  "overview": {"up": 3920, "down": 1349, "limit_up": 155, "limit_down": 3},
  "sectors": {"gain": ["互联网服务", "文化传媒"], "loss": ["保险", "航空机场"]},
  "northbound": {"net_inflow": 12.5, "unit": "亿元", "description": "北向资金净流入"}
}
```

#### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/llm-analysis/dashboard` | Body: `{ "tickers": ["600519","hk00700"], "market": "cn" }`，返回 `{ "results": [ 单股决策, ... ], "summary": { ... } }` |
| GET | `/api/market/daily-review` | Query: `market=cn|us|both`，返回复盘结构 |
| POST | `/api/llm-analysis/run-daily` | 触发一次「每日分析」（决策+复盘+推送），Body 可带 `tickers` 覆盖默认自选 |

### 2.4 Phase 1 环境变量（env.example 新增）

```bash
# ========== 每日智能分析（daily_stock_analysis 移植） ==========
# LLM（至少配置一种）
# OPENAI_API_KEY=
# OPENAI_BASE_URL=https://api.deepseek.com/v1
# OPENAI_MODEL=deepseek-chat
# GEMINI_API_KEY=
# ANTHROPIC_API_KEY=
# ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# 自选股（逗号分隔，与 stz 资产池二选一或合并）
# DAILY_ANALYSIS_TICKERS=600519,000858,hk00700,AAPL

# 交易纪律
# BIAS_THRESHOLD=5.0

# 推送渠道（可选）
# WECHAT_WEBHOOK_URL=
# FEISHU_WEBHOOK_URL=
# TELEGRAM_BOT_TOKEN=
# TELEGRAM_CHAT_ID=
# DINGTALK_WEBHOOK_URL=
# EMAIL_SENDER=
# EMAIL_PASSWORD=
# EMAIL_RECEIVERS=
# PUSHPLUS_TOKEN=

# 每日分析任务（daemon）
# DAILY_ANALYSIS_ENABLED=true
# DAILY_ANALYSIS_TIME=18:00
```

---

## 三、Phase 2 详细移植步骤

### 3.1 新闻搜索服务 `core/search_service.py`

- **职责**：多源搜索（Tavily、SerpAPI、Bocha、Brave）、去重、按时间过滤（NEWS_MAX_AGE_DAYS），返回结构化摘要列表供 builder 拼进 prompt。
- **参考**：`src/search_service.py`。
- **接口**：`search_news(query: str, max_age_days: int = 3, limit: int = 10) -> List[Dict]`，每项含 title、url、snippet、source、date。
- **配置**：`TAVILY_API_KEYS`、`SERPAPI_API_KEYS`、`BOCHA_API_KEYS`、`BRAVE_API_KEYS`（可选），`NEWS_MAX_AGE_DAYS=3`。

### 3.2 筹码与北向资金数据

- **筹码**：若 AkShare 有接口则放在 `data_service` 或 `core/daily_analysis/builder.py` 中调用；否则占位，Phase 2 再接 Tushare/Pytdx。
- **北向资金**：Phase 1 的 `market_review` 已含；若需更细数据可在 `data_service` 增加 `get_northbound_flow()` 等。

### 3.3 决策 builder 接入舆情

- 在 `core/daily_analysis/builder.py` 中，对每只标的调用 `search_service.search_news(ticker_or_name)`，将结果格式化为一段文本注入 prompts；parser 无需改，仍为同一决策结构。

### 3.4 Phase 2 新增/修改清单

| 操作 | 路径 |
|------|------|
| 新增 | `core/search_service.py` |
| 修改 | `core/daily_analysis/builder.py`（接入 search_service） |
| 修改 | `core/daily_analysis/config.py`（新闻相关配置） |
| 修改 | `env.example`（TAVILY_API_KEYS、NEWS_MAX_AGE_DAYS 等） |
| 修改 | `requirements.txt`（tavily-python 等） |

---

## 四、Phase 3 详细移植步骤

### 4.1 决策存储与 AI 回测

- **存储**：新建表或 JSON/Parquet 目录，记录每次决策：`ticker, date, conclusion, action, buy_price, stop_loss, target_price, created_at`。
- **回测脚本**：按 `date` 取决策，取该日后 N 日实际行情，计算：方向是否一致（涨/跌）、是否触及止损、是否触及目标价；汇总方向胜率、止盈率、止损命中率。
- **API**：`GET /api/llm-analysis/backtest?ticker=&days=` 返回上述指标；可选 `POST /api/llm-analysis/backtest` 触发计算并落库。

### 4.2 前端 AI 回测页

- **路径**：`web/src/app/ai-backtest/page.tsx`。
- **内容**：选择标的与回测区间，展示方向胜率、止盈/止损命中率、历史决策列表（表格或时间线）。

### 4.3 GitHub Actions

- **文件**：`.github/workflows/daily-analysis.yml`。
- **步骤**：checkout → 配置 Python → 安装依赖 → 从 Secrets 读取 `OPENAI_API_KEY`、`WECHAT_WEBHOOK_URL` 等 → 执行 `python -m core.daily_analysis.runner` 或调用 `POST /api/llm-analysis/run-daily`（需可外部访问或自托管 API）。
- **触发**：`schedule: cron('0 10 * * 1-5')`（按北京时间可设为 18:00 对应 UTC 10:00）；或 `workflow_dispatch` 手动触发。

### 4.4 Phase 3 新增/修改清单

| 操作 | 路径 |
|------|------|
| 新增 | `core/daily_analysis/storage.py` 或使用现有 `signal_store`/DB 表 |
| 新增 | `core/daily_analysis/backtest.py`（决策回测逻辑） |
| 新增 | `api/routers/llm_analysis.py` 中增加 `/backtest` 端点 |
| 新增 | `web/src/app/ai-backtest/page.tsx` |
| 新增 | `.github/workflows/daily-analysis.yml` |
| 修改 | `docs/` 中补充 GitHub Actions 与 AI 回测说明 |

---

## 五、前端页面规范（Phase 1/3）

### 5.1 决策仪表盘页 `web/src/app/dashboard-llm/page.tsx`

- **布局**：顶部为自选/输入框与「生成」按钮；下方为按股卡片列表。
- **单卡**：结论、操作（买入/观望/卖出）、评分、买卖点（买入价/止损/目标）、检查清单（满足/注意/不满足）、追高/趋势提示、利好与风险摘要。
- **数据**：`POST /api/llm-analysis/dashboard`，展示 `results`。

### 5.2 大盘复盘页 `web/src/app/market-review/page.tsx`

- **布局**：市场选择（cn/us/both）、日期或「当日」；展示指数列表、涨跌家数、板块领涨领跌、北向资金。
- **数据**：`GET /api/market/daily-review?market=cn`。

### 5.3 导航

- 在现有主导航中增加「决策仪表盘」「大盘复盘」入口；Phase 3 增加「AI 回测」。

---

## 六、依赖与 requirements.txt

建议新增（与现有依赖兼容）：

```
openai>=1.0.0
google-generativeai>=0.3.0
tavily-python>=0.3.0
```

可选：`anthropic`（Claude）、Ollama 本地调用为 HTTP，可不加包。SerpAPI/Bocha/Brave 多为 `requests` 调用，已有即可。

---

## 七、测试与验收

### 7.1 单元/集成

- `core/llm_client.py`：mock 响应，测解析与重试。
- `core/daily_analysis/parser.py`：固定 LLM 文本，断言解析出的结论、买卖点、检查清单。
- `core/market_review.py`：mock AkShare/yfinance，测返回结构含 indices、overview、sectors、northbound。
- `core/notification/channels.py`：各渠道 mock Webhook，测请求体格式。

### 7.2 API 验收

- `POST /api/llm-analysis/dashboard`：带 1～2 只 ticker，有 Key 时返回完整 results；无 Key 时返回 503 或明确提示配置。
- `GET /api/market/daily-review?market=cn`：返回 200 及上述复盘结构。
- `POST /api/llm-analysis/run-daily`：触发一次不报错，且可配置为不实际推送（或推送到测试 Webhook）。

### 7.3 前端验收

- 决策仪表盘：能选择标的、请求、展示卡片与检查清单。
- 大盘复盘：能切换市场、展示指数与北向资金。
- Phase 3：AI 回测页能选择标的与区间、展示胜率与命中率。

---

## 八、阶段依赖与排期建议

| 阶段 | 依赖 | 建议工期（人天，估） |
|------|------|----------------------|
| Phase 1 | 无 | 8～12 |
| Phase 2 | Phase 1 决策与 builder | 4～6 |
| Phase 3 | Phase 1 决策落库或 Phase 2 完成后落库 | 4～6 |

实施时优先完成：`core/llm_client.py` → `core/daily_analysis/`（含 builder/prompts/parser/runner）→ `core/market_review.py` → `core/notification/` → API 路由 → 前端两页 → daemon/scheduler 接入 → env 与文档。再按 Phase 2/3 顺序推进舆情、回测与 GitHub Actions。

---

## 九、参考链接与引用

- 参考项目：[ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis)
- 可行性评估：[docs/daily_stock_analysis_移植可行性评估.md](./daily_stock_analysis_移植可行性评估.md)
- 本方案为实施层面的补充，与可行性评估中的「目标范围」「技术栈」「交易纪律」一致；若参考项目有接口变更，以本仓库实际对接为准。
