# daily_stock_analysis 移植完善建议

> 在 [移植详细方案](./daily_stock_analysis_移植详细方案.md) 与 [可行性评估](./daily_stock_analysis_移植可行性评估.md) 基础上，结合当前仓库**已实现状态**与参考项目能力，说明：**如何完全实现**、**方案文档的不足**、**如何进一步完善需求**。

---

## 一、当前实现状态与「完全实现」清单

### 1.1 已实现模块（与方案对照）

| 方案项 | 本仓库实现 | 状态 |
|--------|------------|------|
| `core/llm_client.py` | 已存在，支持 OpenAI 兼容 / Gemini / Anthropic / Ollama | ✅ 已实现 |
| `core/daily_analysis/` | 存在：config, builder, prompts, parser, storage, backtest, `__main__`；入口在 `__init__.py`（run_daily_analysis / run_daily_analysis_from_env） | ✅ 已实现 |
| `core/market_review.py` | 已存在，支持 cn/us/both，指数/板块/北向资金，数据源已绕过 push2 | ✅ 已实现 |
| `core/notification/` | channels（企微/飞书/钉钉/Telegram/邮件/Pushover）、formatter | ✅ 已实现 |
| `core/search_service.py` | 已存在，Tavily 接入；builder 已调用 search_news 注入舆情 | ✅ 已实现 |
| `core/technical_indicators` | 已有，builder 使用 SMA、乖离率、MA 排列 | ✅ 已实现 |
| `api/routers/llm_analysis.py` | dashboard、run-daily、backtest | ✅ 已实现 |
| `api/routers/market.py` | GET /market/daily-review | ✅ 已实现 |
| `web/.../dashboard-llm/page.tsx` | 决策卡片、检查清单、买卖点、利好/风险 | ✅ 已实现 |
| `web/.../market-review/page.tsx` | 指数、概况、领涨领跌、北向、数据日期 | ✅ 已实现 |
| `web/.../ai-backtest/page.tsx` | 标的+回看天数、指标卡片、决策明细表 | ✅ 已实现 |
| daemon + scheduler | setup_daily_analysis_job、daily_analysis_job、DAILY_ANALYSIS_ENABLED/TIME | ✅ 已实现 |
| `.github/workflows/daily-analysis.yml` | 定时 + workflow_dispatch，env 从 Secrets 注入 | ✅ 已实现 |
| `env.example` | LLM、自选、BIAS、推送、TAVILY、DAILY_ANALYSIS_* | ✅ 已实现 |

### 1.2 尚未实现或可加强的部分

| 项目 | 说明 | 建议 |
|------|------|------|
| **方案中的 runner.py** | 方案写的是独立 `runner.py`，实际逻辑在 `daily_analysis/__init__.py` | 无需改，保持现状即可；若希望与方案完全一致，可把 `run_daily_analysis` / `run_daily_analysis_from_env` 挪到 `runner.py` 再在 `__init__.py` 里 re-export |
| **筹码数据** | 方案 Phase 1 写「筹码可占位」；builder 未接入筹码 | 在 builder 中增加「筹码」占位字段（如 `meta["position_summary"] = "待接入"`），或接入 AkShare 等简单接口 |
| **POST /api/llm-analysis/extract-from-image** | 可行性评估 8.3 提到「上传图片提取股票代码」 | 可选 Phase 2：新增端点，调用 Vision 模型解析图片中的代码列表 |
| **决策仪表盘前端** | 未展示「追高/趋势提示」（bias_risk、trend_ok）；未展示汇总 summary（买入/观望/卖出统计）；未提供「附带大盘复盘」勾选 | 见下文「前端完善」 |
| **run-daily 是否推送** | API 的 run-daily 当前会调用 `run_daily_analysis_from_env(send_push=True)`，文档未明确 | 在 API 文档或注释中写明「会按环境变量推送」；可选增加 query 参数 `?push=false` 以关闭推送 |
| **SerpAPI / Bocha / Brave** | 方案 Phase 2 仅写「预留扩展」，search_service 仅 Tavily | 需要时在 search_service 中按方案补充接口约定与 env（SERPAPI_API_KEYS 等） |

---

## 二、移植详细方案的不足

### 2.1 文档与版本

- **缺少「已实现 / 未实现」对照表**：方案以「新建/扩展」为主，未按当前仓库逐项标出哪些已做完、哪些仍待做，导致实施时难以判断进度。
- **参考项目版本未锁定**：未注明以 ZhuLinsen/daily_stock_analysis 的哪个 tag/commit 为准，后续参考项目更新后难以对齐。
- **建议**：在方案开头增加「实现状态表」（如本文 1.1/1.2），并注明「参考版本：daily_stock_analysis @ xxx」。

### 2.2 数据与接口

- **大盘复盘**：方案给出了目标 JSON 结构，但未写「若参考项目有额外字段（如板块涨跌幅数值）」是否保留；当前实现已满足方案，若有需要可再对齐参考项目字段。
- **决策仪表盘**：方案 2.3 单股结构中有 `bias_risk`、`trend_ok`，当前 parser 与 API 是否全部返回未在方案中与前端字段逐项对应。
- **建议**：在方案 2.3 节增加「前端展示字段」一列，标明每个后端字段是否在决策页/回测页展示。

### 2.3 前端规范

- **决策仪表盘**：方案 5.1 提到「追高/趋势提示」，未写具体 UI（如卡片内红/黄标签、文案）；当前前端未展示 bias_risk/trend_ok。
- **大盘复盘**：方案 5.2 未要求「数据日期」展示，已在本轮优化中补充。
- **AI 回测**：方案 4.2/5.3 只写「选择标的与回测区间」，未写「区间」是日期范围还是「回看 N 天」；当前实现为「回看 N 天」。
- **建议**：在方案第五章补充「数据日期」「追高/趋势提示」「summary 统计」「可选大盘复盘」等 UI 规范，并与 2.3 数据模型一一对应。

### 2.4 测试与验收

- **方案 7.1/7.2**：只写了要测的模块和 API，没有给出具体用例（如 mock 数据、期望断言）。
- **建议**：在方案或单独测试说明中增加示例：例如 parser 输入一段固定 LLM 文本，期望解析出的 conclusion、action、buy_price、checklist；market_review mock 某数据源返回，期望 indices/overview/sectors/northbound 结构。

### 2.5 Phase 2 / Phase 3 细节

- **SerpAPI/Bocha/Brave**：仅写「预留扩展」，没有接口签名、返回格式、env 变量名，实施时容易不一致。
- **建议**：在方案 3.1 节补充 `search_news` 的扩展约定（入参不变，返回列表项字段统一），以及各数据源的 env 命名（如 SERPAPI_API_KEYS）。
- **GitHub Actions**：方案 4.3 写了大致步骤，未写「无 Secrets 时是否跳过推送」「失败时是否通知」等策略。
- **建议**：在方案或运维文档中补充：Secrets 不全时仅运行分析不推送、失败时用可选 Slack/邮件通知等。

---

## 三、如何完全实现（实施顺序建议）

### 3.1 立即可做（补齐体验与文档）

1. **决策仪表盘前端**
   - 增加「附带大盘复盘」勾选，请求时传 `include_market_review: true/false`。
   - 展示接口返回的 `summary`（买入/观望/卖出数量、平均分）。
   - 在决策卡片中展示 `bias_risk`、`trend_ok`（追高提示、均线多头排列），与方案 5.1 对齐。
2. **API 与文档**
   - 在 `run-daily` 的 docstring 或 OpenAPI 描述中写明「会根据环境变量向已配置渠道推送决策与复盘」；可选增加 `?push=false` 关闭推送。
3. **方案文档**
   - 在 [移植详细方案](./daily_stock_analysis_移植详细方案.md) 开头增加「实现状态表」（参考本文 1.1/1.2），并注明参考项目版本（如 GitHub tag）。

### 3.2 短期（增强数据与可选能力）

4. **筹码**
   - 在 `builder.build_analysis_input` 中增加筹码占位或简单 AkShare 接口，写入 `meta`，并在 prompts 中留一句「若有筹码数据则附上」。
5. **新闻搜索扩展**
   - 在 `core/search_service.py` 中为 SerpAPI/Bocha/Brave 定义与 Tavily 一致的返回格式，补充 env 示例到 `env.example`。
6. **可选：图片识别**
   - 新增 `POST /api/llm-analysis/extract-from-image`，接收图片文件，调用 Vision 模型返回 `{ "codes": ["600519", ...] }`，供决策仪表盘「从图片导入标的」使用。

### 3.3 中期（验收与可维护性）

7. **测试用例**
   - 为 parser 增加单元测试：固定 LLM 文本 → 断言 conclusion、action、buy_price、stop_loss、target_price、checklist。
   - 为 market_review 增加集成测试：mock 数据源 → 断言返回结构含 date、market、indices、overview、sectors、northbound。
8. **参考项目功能清单对照**
   - 从参考项目 README/模块列出「大盘复盘、决策、推送、舆情、回测、定时」等清单，与本项目逐项打勾，未对齐的列入后续迭代。

---

## 四、进一步完善需求的建议

### 4.1 产品层面

- **自选来源统一**：方案提到「与 stz 资产池二选一或合并」。若希望「决策仪表盘默认用资产池、run-daily 用 DAILY_ANALYSIS_TICKERS」，当前逻辑已支持；若希望「资产池即自选、不再单独 DAILY_ANALYSIS_TICKERS」，可在 run_daily_analysis_from_env 中改为从 stz 资产池 API 拉取列表。
- **复盘与决策的联动**：当前决策页可勾选「附带大盘复盘」并在同一次请求返回；run-daily 也会带复盘并推送。若需「复盘单独定时（如每日 17 点）、决策 18 点」，可在 daemon 中拆成两个任务。
- **免责与合规**：与参考项目一致，在决策页与复盘页底部增加「仅供参考，不构成投资建议」等文案（若尚未存在）。

### 4.2 技术层面

- **LLM 限流与成本**：方案提到「配置开关与限频」；可在 `llm_client` 或 daily_analysis 中增加「每日每标的最多分析 1 次」的缓存或数据库标记，避免重复调用。
- **推送失败重试**：当前 notification 失败仅打日志；可增加重试与「推送失败」汇总在 run_daily 响应中，便于排查。
- **参考项目同步策略**：在文档中说明「移植以接口与数据格式为准，内部实现可简化」；若参考项目有重要更新，可定期对照其 CHANGELOG/Release 做一次差异检查，再决定是否同步。

### 4.3 文档与协作

- **运维手册**：补充「每日分析」章节：如何配置 daemon、如何配置 GitHub Secrets、如何查看 run-daily 日志与推送结果。
- **开发文档**：在 README 或 docs 中增加「daily_stock_analysis 移植模块」小节，列出 core/daily_analysis、market_review、notification、search_service 的职责与入口，便于新人接手。

---

## 五、小结

- **完全实现**：按本文 1.1 的对照表，Phase 1 核心（决策、复盘、推送、舆情、回测、定时、前端三页、daemon、Actions）已实现；完全实现 = 在上述基础上补齐 1.2 与第三节的「立即可做 / 短期 / 中期」项。
- **方案不足**：主要是缺少实现状态表、参考版本、前端 UI 与数据字段的逐项对应、测试用例示例、Phase 2/3 的扩展约定与运维策略；按第二节逐条补充即可进一步完善方案。
- **需求完善**：从产品（自选统一、复盘与决策联动、免责）、技术（限流、推送重试、参考项目同步）、文档（运维、开发结构）三方面按需采纳第四节建议即可。

以上建议可直接用于更新 [移植详细方案](./daily_stock_analysis_移植详细方案.md)，或作为独立附录引用。

---

## 六、实施记录（2026-02）

按第三节「立即可做」与「短期」项已落实：

| 项 | 状态 | 说明 |
|----|------|------|
| 决策仪表盘「附带大盘复盘」勾选 | ✅ | 请求传 `include_market_review`，有数据时展示可折叠复盘块 |
| 决策仪表盘展示 summary | ✅ | 买入/观望/卖出数量、平均分 |
| 决策卡片展示追高/趋势 | ✅ | `meta.bias_risk`、`meta.trend_ok`，builder 写入 `bias_risk` 到 meta |
| run-daily 文档与 push=false | ✅ | docstring 写明推送行为，`?push=false` 关闭推送 |
| 筹码占位 | ✅ | builder 中 `meta.position_summary` 占位，prompt 增加「若有筹码/舆情则参考」 |
| 新闻搜索扩展约定 | ✅ | search_service 模块 docstring 与 env.example 中 SERPAPI/BOCHA/BRAVE 说明 |
