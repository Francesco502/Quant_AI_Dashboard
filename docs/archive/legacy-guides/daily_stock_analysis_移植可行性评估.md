# daily_stock_analysis 功能移植可行性评估与实施方案

> 参考项目：[ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis)  
> 目标：将**主要功能全部引入** Quant_AI_Dashboard，与现有量化系统并存，形成「LLM 智能分析 + 量化交易」一体化能力。

---

## 一、拟引入的主要功能（目标范围）

| 模块 | 功能 | 说明 |
|------|------|------|
| **AI** | 决策仪表盘 | 一句话核心结论 + 精确买卖点位 + 操作检查清单 |
| **分析** | 多维度分析 | 技术面 + 筹码分布 + 舆情情报 + 实时行情 |
| **市场** | 全球市场 | 支持 A股、港股、美股 |
| **复盘** | 大盘复盘 | 每日市场概览、板块涨跌、北向资金 |
| **回测** | AI 回测验证 | 自动评估历史分析准确率，方向胜率、止盈止损命中率 |
| **推送** | 多渠道通知 | 企业微信、飞书、Telegram、钉钉、邮件、Pushover |
| **自动化** | 定时运行 | GitHub Actions 定时执行，无需服务器 |

---

## 二、技术栈与数据来源（目标支持）

| 类型 | 支持 |
|------|------|
| **AI 模型** | Gemini（免费）、OpenAI 兼容、DeepSeek、通义千问、Claude、Ollama |
| **行情数据** | AkShare、Tushare、Pytdx、Baostock、YFinance |
| **新闻搜索** | Tavily、SerpAPI、Bocha、Brave |

---

## 三、内置交易纪律（目标规则）

| 规则 | 说明 |
|------|------|
| 严禁追高 | 乖离率 > 5% 自动提示风险 |
| 趋势交易 | MA5 > MA10 > MA20 多头排列 |
| 精确点位 | 买入价、止损价、目标价 |
| 检查清单 | 每项条件以「满足 / 注意 / 不满足」标记 |

---

## 四、与本项目现有能力对比

| 能力维度 | daily_stock_analysis（拟引入） | Quant_AI_Dashboard（当前） |
|----------|-------------------------------|----------------------------|
| **数据源** | AkShare、Tushare、Pytdx、Baostock、YFinance | AkShare、Tushare、yfinance ✅ 部分重叠 |
| **行情/本地存储** | 多源 + 本地缓存 | data_service + data_store + Parquet ✅ 已有 |
| **AI 预测** | LLM 决策（结论/买卖点/检查清单） | XGBoost/LSTM/Prophet 数值预测 ✅ 已有 |
| **LLM 调用** | Gemini / OpenAI 兼容 / DeepSeek / Claude / Ollama | ❌ 需新增 |
| **新闻/舆情** | Tavily、SerpAPI、Bocha、Brave | ❌ 需新增 |
| **大盘复盘** | 指数 + 板块涨跌 + **北向资金**（cn/us/both） | 有 market_scanner，无复盘报告 ❌ 需新增 |
| **推送通知** | 企微、飞书、Telegram、钉钉、邮件、Pushover | Email/Webhook/Telegram（alert_manager）⚠️ 需扩展 |
| **决策仪表盘** | 一句话结论 + 买卖点位 + 检查清单 | ❌ 需新增 |
| **多维度分析** | 技术面 + 筹码 + 舆情 + 实时行情 | 技术指标已有，筹码/舆情 ❌ 需新增 |
| **全球市场** | A股、港股、美股 | A股/港股已有，美股需统一支持 ⚠️ |
| **AI 回测验证** | 历史决策准确率、止盈止损命中率 | 策略回测已有，LLM 决策回测 ❌ 需新增 |
| **定时/自动化** | GitHub Actions / 本地 cron / Docker | 有 daemon/scheduler ✅ 可接入 |
| **前端** | 决策仪表盘、复盘、设置等 | Next.js Dashboard ✅ 可扩展 |

---

## 五、整体可行性结论

- **全部引入在技术上可行**，建议按**实施阶段**推进，保证每阶段可交付、可验证。
- **可复用现有**：数据服务、市场列表、技术指标、告警通道骨架、前端框架、定时与部署。
- **需要新增/扩展**：LLM 接入层、新闻搜索服务、筹码与北向资金数据、决策报告生成、复盘报告（含北向资金）、推送渠道扩展、决策存储与回测逻辑、前端新页面。
- **风险与成本**：LLM API 费用与密钥管理、第三方新闻 API 配额、数据源扩展（Pytdx/Baostock 若采用）的集成与维护。

---

## 六、各模块可行性及实现要点

### 6.1 AI 决策仪表盘

| 项目 | 说明 |
|------|------|
| **可行性** | ✅ 高 |
| **目标** | 一句话核心结论 + 精确买卖点位（买入价、止损价、目标价）+ 操作检查清单（满足/注意/不满足）。 |
| **思路** | 移植/参考 `src/analyzer.py`、`analyzer_service.py`：拼装行情 + 技术面 + 筹码 + 舆情文本 → 调 LLM → 解析为结构化决策（含交易纪律：乖离率、MA 排列、点位、检查清单）。 |
| **实现要点** | ① 新增 LLM 适配层（Gemini/OpenAI 兼容/DeepSeek/通义/Claude/Ollama，读 env）；② 从 `data_service`、`technical_indicators` 取数并格式化；③ 新 API 如 `POST /api/llm-analysis/dashboard`；④ 前端「决策仪表盘」页。 |
| **依赖** | LLM API Key（至少一种）。 |

### 6.2 多维度分析（技术面 + 筹码 + 舆情 + 实时行情）

| 项目 | 说明 |
|------|------|
| **可行性** | ✅ 高（技术面）/ ⚠️ 中（筹码、舆情） |
| **目标** | 技术面、筹码分布、舆情情报、实时行情统一作为决策输入。 |
| **思路** | 技术面复用现有 `technical_indicators`；筹码与北向资金用 AkShare/Tushare 等接口（参考 daily_stock_analysis 数据层）；舆情由新闻搜索服务提供，注入 LLM prompt。 |
| **实现要点** | ① 封装筹码、北向资金数据接口（可放在 `data_service` 或单独模块）；② 新闻搜索服务（见 6.4）；③ 在决策仪表盘生成流程中汇总四类数据。 |
| **依赖** | 行情数据源；舆情需新闻搜索 API。 |

### 6.3 全球市场（A股、港股、美股）

| 项目 | 说明 |
|------|------|
| **可行性** | ✅ 高 |
| **目标** | 统一支持 A股、港股、美股标的的行情与决策。 |
| **思路** | 现有 `data_service` 已区分资产类型（A股/港股/美股等），需确保全链路（数据、技术指标、LLM 输入、复盘）按市场类型正确路由；美股统一用 YFinance 等保证复权一致。 |
| **实现要点** | ① 自选/资产池支持多市场代码格式（如 600519、hk00700、AAPL）；② 决策与复盘 API 支持 `market=cn|hk|us` 或按标的自动识别。 |
| **依赖** | 无额外 Key，沿用现有数据源。 |

### 6.4 大盘复盘（市场概览 + 板块涨跌 + 北向资金）

| 项目 | 说明 |
|------|------|
| **可行性** | ✅ 高 |
| **目标** | 每日市场概览、板块涨跌、**北向资金**；支持 cn（A股）/ us（美股）/ both。 |
| **思路** | 移植/参考 `src/market_analyzer.py`：主要指数、涨跌家数、板块领涨领跌；北向资金用 AkShare/Tushare 等接口拉取并加入复盘结构。 |
| **实现要点** | ① 新增 `core/market_review.py`（或合并入现有 market 模块），包含北向资金接口；② API `GET /api/market/daily-review?market=cn|us|both`；③ 前端「大盘复盘」页展示指数、板块、北向资金。 |
| **依赖** | 仅行情/宏观数据，北向资金依赖数据源接口可用性。 |

### 6.5 AI 回测验证（历史分析准确率）

| 项目 | 说明 |
|------|------|
| **可行性** | ✅ 中 |
| **目标** | 自动评估历史分析准确率：方向胜率、止盈止损命中率。 |
| **思路** | 持久化每次 LLM 决策（结论、买卖点、时间）；定时或按需对比后续实际涨跌，计算方向胜率与止盈/止损命中率。 |
| **实现要点** | ① 决策结果落库（扩展信号表或专用 `llm_decisions` 表）；② 回测任务读取历史决策 + 行情，计算指标；③ API 与前端「AI 回测」页，与现有策略回测区分。 |
| **依赖** | 先有决策仪表盘与存储。 |

### 6.6 多渠道推送（企微、飞书、Telegram、钉钉、邮件、Pushover）

| 项目 | 说明 |
|------|------|
| **可行性** | ✅ 高 |
| **目标** | 企业微信、飞书、Telegram、钉钉、邮件、Pushover 等，用于决策报告与复盘推送。 |
| **思路** | 参考 `src/notification.py`，按渠道实现发送逻辑；本仓库已有 `core/monitoring/alert_manager.py`（Email、Webhook、Telegram），可在此基础上扩展或新建 `core/notification/` 专供「决策/复盘」推送。 |
| **实现要点** | ① 增加企微、飞书、钉钉、Pushover 等通道；② 推送内容格式（Markdown/卡片）与决策仪表盘、复盘报告一致；③ 配置项：各渠道 Webhook/Token，支持多选。 |
| **依赖** | 各渠道 Webhook/Token 配置。 |

### 6.7 自动化（定时运行，含 GitHub Actions）

| 项目 | 说明 |
|------|------|
| **可行性** | ✅ 高 |
| **目标** | 定时执行每日决策 + 复盘 + 推送；支持 GitHub Actions 无服务器运行。 |
| **思路** | 本仓库已有 daemon/scheduler；新增「每日智能分析」任务：拉取自选、生成决策与复盘、调用推送；GitHub Actions 通过 workflow 定时调用 API 或脚本触发同逻辑。 |
| **实现要点** | ① 封装「每日分析」入口（可 CLI + 可被 API/Actions 调用）；② 可选交易日历（仅交易日执行）；③ 文档与示例：`.github/workflows/daily-analysis.yml`。 |
| **依赖** | 无额外 Key；Actions 需配置仓库 Secrets（LLM、推送等）。 |

### 6.8 内置交易纪律（落地到决策与检查清单）

| 项目 | 说明 |
|------|------|
| **可行性** | ✅ 高 |
| **目标** | 严禁追高（乖离率>5% 提示）、趋势交易（MA5>MA10>MA20）、精确点位、检查清单标记。 |
| **思路** | 在决策生成流程中：① 计算乖离率与 MA 排列，传入 LLM 并在解析结果中体现「追高风险」「趋势是否多头」；② LLM 输出结构化买入价/止损价/目标价；③ 检查清单项由 LLM 或规则产出，统一为「满足/注意/不满足」。 |
| **实现要点** | ① 在 `technical_indicators` 或决策输入中增加乖离率、MA 排列；② Prompt 与解析 schema 固定包含：结论、买卖点、检查清单及每项状态。 |
| **依赖** | 无额外 Key。 |

---

## 七、实施阶段规划（全部功能分阶段交付）

在**全部引入**前提下，建议按以下阶段实施，便于迭代与验收：

| 阶段 | 内容 | 交付物 |
|------|------|--------|
| **Phase 1** | 决策仪表盘（含交易纪律）、大盘复盘（含北向资金）、全球市场支持、推送渠道扩展、自动化入口 | LLM 分析服务、market_review、notification 扩展、每日分析任务、前端决策页+复盘页 |
| **Phase 2** | 多维度分析完善（筹码、北向资金数据）、新闻/舆情搜索接入决策 prompt | search_service、筹码/北向数据接口、决策 prompt 含舆情 |
| **Phase 3** | AI 回测验证（历史决策准确率、止盈止损命中率）、GitHub Actions 示例与文档 | 决策存储、回测脚本、API 与前端「AI 回测」、.github/workflows 示例 |

---

## 八、技术实现要点

### 8.1 目录与依赖

- **不直接拷贝整个 daily_stock_analysis 仓库**，按模块移植并接入本仓库：
  - `src/analyzer.py`、`analyzer_service.py` → `core/llm_analysis.py` 或 `core/daily_analysis/`（决策仪表盘 + 交易纪律）。
  - `src/market_analyzer.py` + 北向资金 → `core/market_review.py`。
  - `src/notification.py` → 抽取各渠道，合并到 `core/monitoring/` 或新建 `core/notification/`。
  - `src/search_service.py` → `core/search_service.py`。
  - `src/config.py` 中 LLM、新闻、推送、市场相关配置 → 并入本仓库 `.env` 与配置模块。
- **依赖**：`requirements.txt` 增加 LLM 与搜索相关（如 `openai`、`tavily-python` 等），与现有依赖兼容。

### 8.2 数据与配置

- **行情与指标**：统一经 `core/data_service.py`、`core/technical_indicators.py`，并扩展筹码、北向资金（如通过 AkShare/Tushare）。
- **自选股/资产池**：与现有 stz asset-pool 或配置 watchlist 统一，支持 A股、港股、美股代码。
- **环境变量**：新增例如 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`GEMINI_API_KEY`、`TAVILY_API_KEYS`、`WECHAT_WEBHOOK_URL`、`FEISHU_WEBHOOK_URL`、`BIAS_THRESHOLD`（默认 5）等，文档中说明必填/可选。

### 8.3 API 设计建议

- `POST /api/llm-analysis/dashboard`  
  - Body: `{ "tickers": ["600519","hk00700","AAPL"], "market": "cn" }`  
  - 返回：每只股票的决策（结论、买卖点、检查清单、追高/趋势提示等）。
- `GET /api/market/daily-review?market=cn|us|both`  
  - 返回：指数、涨跌家数、板块领涨领跌、**北向资金**、可选 LLM 摘要。
- `POST /api/llm-analysis/extract-from-image`（可选）  
  - 表单上传图片，返回 `{ "codes": ["600519", ...] }`。
- 推送：由 daemon/scheduler 或 GitHub Actions 定时调用「每日分析」入口，再调用扩展后的 notification 发送决策与复盘。

### 8.4 前端

- 在 Next.js 中新增：
  - **决策仪表盘**：展示 LLM 结论、买卖点、检查清单（满足/注意/不满足）、追高与趋势提示。
  - **大盘复盘**：展示指数、板块、北向资金、涨跌家数及可选摘要。
  - **AI 回测**（Phase 3）：历史决策准确率、止盈止损命中率。

---

## 九、风险与注意事项

- **LLM 成本与限流**：按调用量计费，建议配置开关与限频（如每日一次批量决策），并支持选用免费/低成本模型（如 Gemini、Ollama）。
- **合规与免责**：决策内容仅供研究参考，不构成投资建议；前端与文档需明确免责（与 daily_stock_analysis 一致）。
- **数据源差异**：Pytdx、Baostock 若引入，需评估与本项目现有 AkShare/Tushare/yfinance 的互补与维护成本；北向资金依赖数据源稳定性。
- **版本与兼容**：参考项目迭代较快，移植以「接口与数据格式」为主，内部实现可简化或替换，便于后续独立演进。

---

## 十、下一步建议

1. **确认 Phase 1 范围**：决策仪表盘 + 大盘复盘（含北向资金）+ 推送扩展 + 自动化入口，作为首期交付。
2. **新建分支**，按 Phase 1 实现：
   - `core/llm_analysis.py`（或 `core/daily_analysis/`）
   - `core/market_review.py`（含北向资金）
   - 扩展 `core/monitoring` 或新增 `core/notification`
   - 新 API 路由与前端「决策仪表盘」「大盘复盘」页
   - 每日分析任务与调用入口
3. **更新 `.env.example` 与文档**：LLM、新闻、推送、BIAS_THRESHOLD 等配置说明。
4. **Phase 2/3** 按上表依次推进：舆情、AI 回测、GitHub Actions 示例。

若需要从某一模块开始落地（例如先做决策仪表盘或先做大盘复盘+北向资金），可在此基础上拆出更细的文件级改动清单与接口定义。
