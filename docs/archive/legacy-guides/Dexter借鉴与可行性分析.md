# Dexter 项目借鉴与可行性分析

本文档基于对 **dexter-main**（Dexter：面向金融研究的自主 AI Agent）的阅读，分析其可被 **Quant_AI_Dashboard** 借鉴或优化的内容，并给出可行性评估与实施建议。

---

## 一、Dexter 项目概览

| 维度 | 内容 |
|------|------|
| 定位 | CLI 金融研究 Agent：任务规划、自主执行工具、自检与迭代 |
| 技术栈 | TypeScript、Bun、Ink（React for CLI）、LangChain |
| 核心能力 | 自然语言 → 任务分解 → 多轮工具调用 → Scratchpad 记录 → 最终答案单独生成 |
| 数据/工具 | Financial Datasets API、Exa/Tavily 搜索、Playwright 浏览器、SKILL.md 技能 |
| 运维/质量 | Scratchpad JSONL 调试、LangSmith Evals、LLM-as-judge 评分、可选 WhatsApp 网关 |

与本项目对比：

- **Quant_AI_Dashboard**：Python/FastAPI、Web 仪表盘、每日分析（单轮 LLM + 固定上下文）、大盘复盘、预测与回测；**当前无「多轮工具调用」Agent 循环**。
- **Dexter**：TS/Bun、CLI、多轮 Agent 循环、统一 financial_search 元工具、Skills、Evals。

因此借鉴重点是：**在不改技术栈的前提下，把 Dexter 中与「架构模式、可观测性、缓存、评估、扩展点」相关的思路迁移到 Python 侧**；Agent 循环与工具链可作为后续增强方向。

---

## 二、可借鉴点与可行性分析

### 1. Scratchpad / 工具调用与推理日志（高可行性）

**Dexter 做法**  
- 每次查询生成一个 JSONL 文件（`.dexter/scratchpad/`），按行记录：`init`（原始问题）、`tool_result`（工具名、参数、原始结果）、`thinking`（推理片段）。  
- 作为单次会话的「单一事实来源」，用于调试、审计和后续「最终答案」生成的上下文。

**可借鉴到本项目**  
- 在 **每日分析 / 单次 LLM 调用** 流程中，增加可选「分析过程日志」：例如写入 `data/scratchpad/` 或 `logs/llm/`，按请求 ID 或时间戳命名，记录：请求参数、拼装后的 prompt 摘要、模型与 token 用量、返回结论摘要。  
- 若未来增加 **多步 Agent**（见下），则改为按「会话」记录每步的 tool 调用与结果，格式可对齐 Dexter 的 init / tool_result / thinking。

**可行性**  
- **可行性：高**。纯日志与文件写入，与现有 `core.daily_analysis`、`core.llm_client` 无冲突。  
- **工作量：小**（约 0.5～1 人天）。  
- **建议**：先做「单次分析请求」的轻量 scratchpad（请求入参 + 上下文摘要 + 结论 + 用时），为后续 Agent 留扩展字段。

---

### 2. API 响应文件缓存（高可行性）

**Dexter 做法**  
- `src/utils/cache.ts`：按 `(endpoint, params)` 生成确定性的缓存键（含 ticker 前缀便于查看），存 JSON 文件到 `.dexter/cache/`。  
- 读缓存时校验结构（`CacheEntry`），损坏则删除文件并回退到请求。  
- 调用方通过 `cacheable: true` 决定是否走缓存，缓存层不关心业务含义。

**可借鉴到本项目**  
- 当前已有 **MultiLevelCache**（内存 + 磁盘 pickle）。可在此基础上增加「**按接口+参数键的 API 响应缓存**」：  
  - 键：例如 `prices/{ticker}_{interval}_{limit}.json` 或 `market_review/{market}.json`。  
  - 值：统一结构 `{ endpoint, params, data, cached_at }`，便于过期与校验。  
- 适用于：`core.data_service` 的价格/OHLCV、`core.market_review` 的复盘结果、第三方数据接口等。

**可行性**  
- **可行性：高**。与现有 `multi_level_cache`、`data_service` 兼容，可做成可选包装器。  
- **工作量：中**（约 1～2 人天）。需统一键生成规则与 TTL 策略（如按数据类型区分过期时间）。

---

### 3. 工具注册表 + 富描述注入 System Prompt（中高可行性，依赖是否上 Agent）

**Dexter 做法**  
- `src/tools/registry.ts`：统一注册所有工具，每个工具带「富文本描述」（何时用、何时不用、示例）。  
- 在 `buildSystemPrompt()` 中把 `buildToolDescriptions(model)` 注入，使 LLM 明确知道有哪些工具及使用策略。

**可借鉴到本项目**  
- **当前**：无工具调用，仅有「单轮 prompt + 固定上下文」。若保持现状，可先做「**结构化 prompt 模块**」：把「数据说明」「大盘复盘说明」「技术指标说明」等写成常量或小模块，在 `daily_analysis` 的 builder 里组装，便于维护和 A/B。  
- **若引入 Agent**：在 Python 侧实现 **Tool Registry**：工具名、参数 schema、富描述；在构造 system prompt 时自动拼接「## 可用工具」段落。LangChain/LlamaIndex 等均可选，也可自建轻量版。

**可行性**  
- **可行性：高**（仅 prompt 模块）或 **中高**（含 Agent 工具注册）。  
- **工作量**：仅 prompt 模块为小（约 0.5 人天）；若含 Agent 则中（约 2～3 人天）。

---

### 4. Financial 元工具：自然语言 → 子工具路由（中可行性）

**Dexter 做法**  
- `financial_search`：用户输入一条自然语言查询，由 **LLM + 内部工具列表** 做一次 tool-calling，路由到 `get_stock_price`、`get_income_statements`、`get_key_ratios` 等，再汇总结果返回。

**可借鉴到本项目**  
- 思路：提供一个 **「自然语言财务查询」API**，背后用 LLM 将句子解析为「要查的标的 + 指标类型 + 时间范围」，再映射到现有或新增接口（如 `/api/data/prices`、未来基本面/财报接口）。  
- 前提：需要足够多的**结构化数据接口**（价格、基本面、财报摘要等）；当前项目以价格与技术面为主，可先做「价格+复盘+新闻」的轻量版路由。

**可行性**  
- **可行性：中**。依赖数据接口的完善程度。  
- **工作量：中高**（约 2～4 人天）。建议先做「有限子集」（如仅价格+复盘），再逐步扩展。

---

### 5. Skills（SKILL.md）工作流（高可行性）

**Dexter 做法**  
- 技能以 **SKILL.md** 文件存在，YAML frontmatter（name, description）+ Markdown 正文（步骤、检查清单、注意事项）。  
- 启动时扫描 `src/skills/`、`~/.dexter/skills`、`.dexter/skills`，把技能元数据注入 system prompt，通过 `skill` 工具按名调用，每次查询每技能最多执行一次。

**可借鉴到本项目**  
- 在仓库中增加 `core/skills/` 或 `config/skills/` 目录，放置例如 `dcf_valuation.md`、`trend_summary.md`：  
  - frontmatter：`name`, `description`；  
  - 正文：步骤列表、所需数据、输出格式要求。  
- **不一定要有 tool-calling**：可在「每日分析」或「研报摘要」的 system 里加入「可用技能列表 + 简短说明」，让 LLM 在回复中按技能步骤组织内容；或未来与 Agent 结合时再做成可调用技能。

**可行性**  
- **可行性：高**。仅涉及文件扫描、YAML 解析和 prompt 拼接，与现有栈兼容。  
- **工作量：中**（约 1～2 人天）。需约定目录规范与 frontmatter 字段。

---

### 6. Evals：数据集 + LLM-as-judge（高可行性）

**Dexter 做法**  
- CSV 数据集（question, reference_answer, question_type, rubric 等），`src/evals/run.ts` 用 LangSmith 跑 batch，对每个问题调用 Agent，再用 **LLM-as-judge**（带 criteria/rubric）打分，并展示进度与准确率。

**可借鉴到本项目**  
- **数据集**：维护一份 CSV/JSON，例如（问题、期望结论要点、市场类型、可选 rubric）。  
- **运行器**：Python 脚本遍历题目，调用当前「每日分析」或未来的 Agent 接口，收集模型输出。  
- **评分**：用现有 `llm_client` 再调一次 LLM，传入「题目 + 参考要点 + 模型输出」，要求输出 0～1 或 1～5 分 + 简短理由；可写回 JSON 便于分析。  
- LangSmith 可选；无 LangSmith 也可本地写 JSON 报告。

**可行性**  
- **可行性：高**。与现有 LLM 与 API 完全兼容。  
- **工作量：中**（约 2～3 人天）。需设计题目格式、rubric 和评分 prompt，并做简单报告汇总。

---

### 7. Context 管理与 Token 阈值清理（与 Agent 绑定）

**Dexter 做法**  
- 迭代过程中保留「完整工具结果」在上下文中；当估计 token 超过阈值时，**清除最旧的若干条 tool 结果**（scratchpad 内 in-memory 标记），仅保留最近 N 条，再继续迭代；最终答案阶段仍可从 scratchpad 读全量结果。

**可借鉴到本项目**  
- 当前无多轮 Agent，**暂不适用**。  
- **若未来做 Agent**：在 Python 侧实现「按轮次/按条数或 token 估计的上下文窗口」与「清除最旧 tool 结果」的逻辑即可，思路直接可复用。

**可行性**  
- **可行性：高**（在引入 Agent 的前提下）。  
- **工作量：中**（约 1～2 人天），与 Agent 开发一起做。

---

### 8. 工具调用限制与防循环（与 Agent 绑定）

**Dexter 做法**  
- Scratchpad 中 `canCallTool`、`recordToolCall`、`getToolUsageStatus`：按工具统计调用次数，并做「查询相似度」（如 Jaccard）检测重复问题；超过建议次数时**不禁止**调用，而是在 prompt 中注入警告，引导换工具或收尾。

**可借鉴到本项目**  
- 仅当存在「多步工具调用」时才有意义。  
- 实现方式：在 Agent 的每步执行前，检查该工具调用次数与历史查询相似度，若超限则往 prompt 追加一段「建议收尾或换策略」的说明；可选在 scratchpad 中记录每次调用的 query 摘要。

**可行性**  
- **可行性：高**（在已有 Agent 的前提下）。  
- **工作量：小～中**（约 1 人天）。

---

### 9. 最终答案单独一轮 LLM 调用（与 Agent 绑定）

**Dexter 做法**  
- 工具循环结束后，用 **buildFinalAnswerPrompt** 将 scratchpad 中的全部工具结果拼成一段上下文，再调用一次 LLM（**不绑定 tools**），只生成最终自然语言答案。

**可借鉴到本项目**  
- 若未来实现 Agent：在「规划+工具执行」循环结束后，将「所有工具输出 + 原始问题」拼成一条 prompt，调用现有 `llm_client.chat_completion` 一次，得到最终回复。  
- 与当前「单轮分析」的体验一致，只是数据来源从「builder 固定上下文」变为「Agent 工具结果」。

**可行性**  
- **可行性：高**。  
- **工作量：小**（约 0.5 人天），与 Agent 最后一环一起做。

---

### 10. 多 LLM 提供商（OpenAI / Anthropic / Google / OpenRouter / Ollama）（高可行性）

**Dexter 做法**  
- 通过模型名前缀选择提供商（如 `claude-` → Anthropic），支持 OpenAI、Anthropic、Google、xAI、OpenRouter、Ollama；Anthropic 使用 prompt caching 以节省成本。

**可借鉴到本项目**  
- 当前已有 **OpenAI 兼容** 与 **Gemini**。可扩展：  
  - 在 `core.llm_client` 中增加 **Anthropic**、**OpenRouter**、**Ollama** 等分支；  
  - 通过环境变量或配置选择默认模型/提供商；  
  - 若使用 Anthropic，可查阅其 API 是否支持 system prompt 缓存并启用。

**可行性**  
- **可行性：高**。  
- **工作量：低～中**（约 1～2 人天），按需增加 provider 与配置项。

---

### 11. SOUL.md / 用户身份与投资哲学（高可行性）

**Dexter 做法**  
- 支持用户覆盖 `~/.dexter/SOUL.md`，内容会拼进 system prompt 的「Identity」段落，用于定制助手人设与投资哲学。

**可借鉴到本项目**  
- 支持可选文件，例如项目根目录或配置目录下的 `soul.md` / `identity.md`；若存在则在构建「每日分析」或 Agent 的 system prompt 时追加一段「身份与原则」。  
- 可用于区分不同团队/个人的风格（保守/激进、偏技术面/基本面等）。

**可行性**  
- **可行性：高**。  
- **工作量：小**（约 0.5 人天）。

---

### 12. 多通道推送（如 WhatsApp）（中可行性）

**Dexter 做法**  
- 通过 Baileys 等库做 WhatsApp 网关，用户扫码绑定，向「自己」发消息即由 Dexter 处理并回复。

**可借鉴到本项目**  
- 当前已有 **core.notification**（企微、飞书、钉钉、Telegram、邮件等）。若需 **WhatsApp**，可新增一个 channel，对接类似 Baileys 或官方 Business API；需考虑合规与运维成本。

**可行性**  
- **可行性：中**。依赖选型与政策。  
- **工作量：中**（约 2～3 人天），建议作为可选增强。

---

## 三、实施优先级建议

| 优先级 | 项 | 可行性 | 工作量 | 说明 |
|--------|----|--------|--------|------|
| P0 | Scratchpad / 分析过程日志 | 高 | 小 | 立刻提升可观测性与可调试性 |
| P0 | API 响应文件缓存（含 ticker 等键） | 高 | 中 | 降延迟、减重复请求，与现有多级缓存兼容 |
| P1 | Evals（数据集 + LLM-as-judge） | 高 | 中 | 持续评估分析/决策质量 |
| P1 | Skills（SKILL.md）目录与 prompt 注入 | 高 | 中 | 可扩展工作流与 prompt 管理 |
| P1 | 多 LLM 提供商扩展 | 高 | 低～中 | 按需增加 Anthropic、OpenRouter、Ollama |
| P1 | SOUL.md / 身份文档 | 高 | 小 | 低成本定制分析风格 |
| P2 | 工具注册表 + 富描述（含未来 Agent） | 高 | 中 | 为将来多步 Agent 打基础 |
| P2 | Financial 元工具（自然语言→子工具） | 中 | 中高 | 依赖数据接口完善 |
| P2 | Context 管理 / 工具限流 / 最终答案单独调用 | 高 | 中 | 与「是否上 Agent」一起规划 |
| P3 | WhatsApp 等新推送通道 | 中 | 中 | 按需求与合规决定 |

---

## 四、总结

- **无需改技术栈**即可落地的有：Scratchpad 式日志、API 响应缓存、Evals、Skills 目录、多 LLM 提供商、SOUL.md。  
- **与「多步 Agent」强绑定**的有：工具注册表、context 管理、工具限流、最终答案单独一轮、Financial 元工具（若做成 Agent 的入口）。  
- 建议先做 **P0**（日志 + 缓存）和 **P1**（Evals、Skills、多提供商、SOUL），再视需求决定是否引入轻量 Agent 并复用 Dexter 的循环与防循环、最终答案生成等模式。

以上分析基于对 dexter-main 源码与 Quant_AI_Dashboard 现有结构的阅读，实施时可根据实际排期与资源微调优先级。
