# Dexter 借鉴优化实施方案（详细）

本文档在《Dexter借鉴与可行性分析》基础上，给出**可执行的具体实施方案**：涉及的新增文件、修改点、数据结构、环境变量与验收标准，并按阶段拆分任务与工时。

---

## 总体阶段与依赖关系

```
Phase 0 (P0) ────────────────────────────────────────────────
  ├── 0.1 Scratchpad 分析过程日志
  └── 0.2 API 响应文件缓存

Phase 1 (P1) ────────────────────────────────────────────────
  ├── 1.1 Evals 数据集 + LLM-as-judge
  ├── 1.2 Skills（SKILL.md）目录与 prompt 注入
  ├── 1.3 多 LLM 提供商扩展
  └── 1.4 SOUL.md 身份文档

Phase 2 (P2) ────────────────────────────────────────────────
  ├── 2.1 结构化 Prompt 模块（工具/数据描述）
  ├── 2.2 Financial 元工具（自然语言→子工具路由）
  └── 2.3 Agent 相关（Context 管理 / 工具限流 / 最终答案单独调用）— 可选，与「是否上 Agent」同步规划
```

- **P0** 与现有代码无强依赖，可并行开发。
- **P1** 中 1.2 Skills、1.4 SOUL 会改动 `core/daily_analysis/prompts.py` 的 system 构建逻辑，建议在 0.1 Scratchpad 接入 `run_daily_analysis` 之后再做，便于一次验证。
- **P2** 依赖 P1 的 prompt 扩展与数据接口成熟度。

---

## Phase 0：Scratchpad + API 响应缓存

### 0.1 Scratchpad 分析过程日志

**目标**：每次「每日分析」请求（单标的或批量）产生一条可追溯的记录，便于调试、审计与后续扩展 Agent 时的 tool 记录格式对齐。

#### 0.1.1 目录与文件

| 类型 | 路径 | 说明 |
|------|------|------|
| 新增模块 | `core/scratchpad.py` | Scratchpad 写入、读取、条目格式定义 |
| 配置/目录 | `data/scratchpad/` 或 `logs/llm/scratchpad/` | 存放 JSONL 文件，需加入 `.gitignore` |

#### 0.1.2 数据结构

**单条 JSONL 行（与 Dexter 对齐，便于后续扩展）**：

```json
{"type":"init","request_id":"req_xxx","timestamp":"2026-02-26T12:00:00","ticker":"600519","market":"cn","text_context_preview":"标的代码: 600519..."}
{"type":"llm_call","request_id":"req_xxx","timestamp":"...","model":"gemini-1.5-flash","prompt_token_estimate":1200,"response_preview":"{\"conclusion\":\"...\"}"}
{"type":"result","request_id":"req_xxx","timestamp":"...","action":"观望","score":65,"elapsed_ms":3200}
```

- `type`：`init`（请求入参）、`llm_call`（本次 LLM 调用摘要）、`result`（解析后的决策摘要）；预留 `tool_result`、`thinking` 供未来 Agent 使用。
- `request_id`：同一请求内所有行一致，格式建议 `{date}-{short_hash}` 或 UUID。
- 大文本只存 `preview`（例如前 500 字符），避免单文件过大。

#### 0.1.3 接口设计（core/scratchpad.py）

```python
# 伪代码示意
def create_scratchpad(request_id: str, ticker: str, market: str, text_context_preview: str) -> str:
    """创建本次请求的 scratchpad 文件路径，并写入 init 行。返回 filepath。"""

def append_llm_call(filepath: str, model: str, prompt_token_estimate: int, response_preview: str) -> None:
    """追加 llm_call 行。"""

def append_result(filepath: str, action: str, score: Optional[float], elapsed_ms: int) -> None:
    """追加 result 行。"""

def is_scratchpad_enabled() -> bool:
    """根据环境变量 SCRATCHPAD_ENABLED（默认 true）决定是否写入。"""
```

#### 0.1.4 修改点

| 文件 | 修改内容 |
|------|----------|
| `core/daily_analysis/__init__.py` | 在 `_analyze_single` 内：若 `is_scratchpad_enabled()`，则先 `create_scratchpad(...)`，在 `llm_client.chat_completion` 前后记录时间，调用后 `append_llm_call`，解析后 `append_result`。 |
| `env.example` | 增加 `# SCRATCHPAD_ENABLED=true` 与 `# SCRATCHPAD_DIR=data/scratchpad`（可选）。 |

#### 0.1.5 验收标准

- 开启 `SCRATCHPAD_ENABLED=true` 时，每次单标的分析在 `data/scratchpad/` 下生成一个 JSONL 文件，且包含 `init`、`llm_call`、`result` 三型行。
- 关闭 `SCRATCHPAD_ENABLED=false` 时，不写文件、不抛错。
- 单文件可被人工或脚本按行解析，且 `request_id` 一致。

#### 0.1.6 预估工时

**0.5～1 人天**（含单元测试或手测）。

---

### 0.2 API 响应文件缓存

**目标**：对「按接口+参数」可复用的数据（如价格、大盘复盘）增加一层 JSON 文件缓存，带 TTL 与结构校验，与现有 `MultiLevelCache` 并存，不替换现有逻辑。

#### 0.2.1 目录与文件

| 类型 | 路径 | 说明 |
|------|------|------|
| 新增模块 | `core/api_response_cache.py` | 键生成、读写、TTL、结构校验 |
| 缓存目录 | `data/api_cache/` 或 `cache/api/` | 子目录按 endpoint 划分，如 `prices/`、`market_review/` |

#### 0.2.2 缓存键与值格式

- **键**：`{endpoint}/{param_hash}.json`，其中 `param_hash` 由 `endpoint + 有序 params` 做 MD5 取前 12 位；若 params 含 `ticker`，可在文件名前加 `{TICKER}_` 便于排查。
  - 例：`prices/600519_a1b2c3d4e5f6.json`、`market_review/cn_f1e2d3c4b5a6.json`。
- **值**（单文件 JSON）：
  ```json
  {
    "endpoint": "prices",
    "params": {"ticker": "600519", "days": 365},
    "data": { ... },
    "cached_at": "2026-02-26T12:00:00Z"
  }
  ```

#### 0.2.3 TTL 策略（可配置）

| endpoint 类型 | 默认 TTL | 说明 |
|---------------|----------|------|
| prices / ohlcv | 300（5 分钟） | 行情类可适当短 |
| market_review | 600（10 分钟） | 复盘按日可更长 |
| 通用 | 300 | 未配置时默认 |

建议通过 `API_CACHE_TTL_SECONDS` 或按 endpoint 的映射（如 `API_CACHE_TTL_PRICES=300`）读取。

#### 0.2.4 接口设计（core/api_response_cache.py）

```python
def get_cached(endpoint: str, params: dict) -> Optional[dict]:
    """若存在且未过期且结构合法，返回 entry["data"]，否则 None。若文件损坏则删除并返回 None。"""

def set_cached(endpoint: str, params: dict, data: dict) -> None:
    """写入 JSON 文件，含 endpoint、params、data、cached_at。"""

def get_ttl_seconds(endpoint: str) -> int:
    """根据 endpoint 或环境变量返回 TTL（秒）。"""
```

#### 0.2.5 修改点

| 文件 | 修改内容 |
|------|----------|
| `core/data_service.py` | 在 `load_price_data` 入口（或更底层如 `_load_price_data_remote` 返回前）：若调用方传入 `use_api_cache=True`（或通过全局配置），则先 `get_cached("prices", {"tickers": tickers, "days": days})`；命中则直接转成 DataFrame 返回；未命中则走现有逻辑，并在返回前 `set_cached(...)`。注意：params 需可序列化（如 tickers 转为 tuple 或排序后 list）。 |
| `core/market_review.py` | 在 `daily_review` 入口：先 `get_cached("market_review", {"market": market})`；未命中则执行现有逻辑，写入 `set_cached("market_review", {"market": market}, result_dict)`。 |
| `core/daily_analysis/builder.py` | 调用 `load_price_data` 时传入 `use_api_cache=True`（若 data_service 支持）；或保持不传，由 data_service 内部根据环境变量决定是否启用。 |
| `env.example` | 增加 `# API_RESPONSE_CACHE_ENABLED=true`、`# API_CACHE_DIR=data/api_cache`、`# API_CACHE_TTL_PRICES=300`、`# API_CACHE_TTL_MARKET_REVIEW=600`。 |

#### 0.2.6 验收标准

- 启用缓存且 TTL 内重复请求同一 params 时，不发起新的 akshare/yfinance 请求（可通过日志或 mock 验证）。
- 缓存文件可读，且 `cached_at` 与内容一致；过期后再次请求会重新拉取并覆盖写入。
- 损坏的 JSON 文件会被删除并回退到实时请求，不抛错。

#### 0.2.7 预估工时

**1～2 人天**（含 data_service / market_review 两处接入与 TTL 配置）。

---

## Phase 1：Evals、Skills、多 LLM、SOUL

### 1.1 Evals：数据集 + LLM-as-judge

**目标**：维护一份「问题 + 参考要点」数据集，用 Python 脚本调用当前分析接口，再用 LLM 对「模型输出 vs 参考」打分并输出报告。

#### 1.1.1 目录与文件

| 类型 | 路径 | 说明 |
|------|------|------|
| 数据集 | `evals/dataset/llm_analysis_evals.csv` | 列：question, ticker, market, reference_points, question_type, rubric（可选） |
| 运行器 | `evals/run_evals.py` | 读 CSV、调 API 或直接调 `run_daily_analysis`、收集输出、调 LLM 判分、写报告 |
| 评分 prompt | `evals/prompts/judge_system.txt` 或内联在 run_evals.py | 规定输出格式（分数 + 理由） |

#### 1.1.2 数据集格式示例（CSV）

```csv
question,ticker,market,reference_points,question_type
"基于当前技术面给出操作建议","600519","cn","应包含 action/score/buy_price 等字段; 若乖离率超阈值需提示风险","decision"
"简述近期走势并给出结论","000858","cn","结论明确; 有 checklist 或 highlights","summary"
```

- `reference_points`：用分号分隔的要点，供 judge 对照。
- `rubric` 可选，可为 JSON 字符串，列出更细的 criteria。

#### 1.1.3 运行器流程（evals/run_evals.py）

1. 读取 `evals/dataset/llm_analysis_evals.csv`。
2. 对每行：用 `ticker`+`market` 调用 `run_daily_analysis(tickers=[ticker], market=market)` 或对应 API；取该 ticker 的 `decision` 与 `raw_text`。
3. 构造 judge prompt：题目 + reference_points + 模型输出；调用 `llm_client.chat_completion`，要求输出 JSON：`{"score": 0-1, "reason": "..."}`。
4. 汇总每题得分，写入 `evals/reports/evals_report_{timestamp}.json`（及可选 CSV 摘要）。

#### 1.1.4 验收标准

- 运行 `python -m evals.run_evals`（或 `python evals/run_evals.py`）可完成一轮评估并生成报告文件。
- 报告中包含每题的 score、reason 以及整体平均分。

#### 1.1.5 预估工时

**2～3 人天**（含数据集样例、judge prompt 调优、报告格式）。

---

### 1.2 Skills（SKILL.md）目录与 prompt 注入

**目标**：通过「技能目录 + YAML frontmatter + Markdown 正文」扩展 system prompt，使每日分析（或后续 Agent）能按技能组织输出。

#### 1.2.1 目录与文件

| 类型 | 路径 | 说明 |
|------|------|------|
| 技能目录 | `core/skills/` 或 `config/skills/` | 每个子目录一个技能，内含 `SKILL.md` |
| 加载器 | `core/skills/registry.py` | 扫描目录、解析 frontmatter、返回 name+description+body |
| 示例技能 | `core/skills/trend_summary/SKILL.md` | 示例：趋势摘要技能 |

#### 1.2.2 SKILL.md 格式

```yaml
---
name: trend_summary
description: 对标的近期趋势与均线关系做简要总结，并给出多空倾向。
---
# 趋势摘要技能
- 步骤1：根据 MA5/10/20 描述短期趋势。
- 步骤2：结合乖离率判断是否超买/超卖。
- 步骤3：输出一句话结论与操作倾向。
```

- 扫描范围：项目内 `core/skills/`；可选用户目录 `~/.quant/skills/`（若存在）。

#### 1.2.3 接口设计（core/skills/registry.py）

```python
def discover_skills() -> List[dict]:
    """返回 [{"name": "...", "description": "...", "path": "..."}, ...]。"""

def build_skills_prompt_section() -> str:
    """返回用于拼接到 system prompt 的字符串，格式：## 可用技能\n- **name**: description\n..."""
```

#### 1.2.4 修改点

| 文件 | 修改内容 |
|------|----------|
| `core/daily_analysis/prompts.py` | 在 `build_messages` 中：若 `discover_skills()` 非空，则调用 `build_skills_prompt_section()`，将结果追加到 `system_prompt`（如「## 可用技能」段落）。可加开关 `SKILLS_ENABLED=true`。 |
| `env.example` | 增加 `# SKILLS_ENABLED=true`、`# SKILLS_DIR=core/skills`（可选）。 |

#### 1.2.5 验收标准

- 在 `core/skills/trend_summary/SKILL.md` 存在时，每日分析 system 中包含「可用技能」及该技能的 name/description。
- 关闭 `SKILLS_ENABLED=false` 时，不扫描、不追加段落。

#### 1.2.6 预估工时

**1～2 人天**（含 registry、frontmatter 解析、prompts 集成）。

---

### 1.3 多 LLM 提供商扩展

**目标**：在现有 OpenAI 兼容、Gemini 基础上，增加 Anthropic、OpenRouter、Ollama 等，通过环境变量或模型名前缀选择。

#### 1.3.1 修改点

| 文件 | 修改内容 |
|------|----------|
| `core/llm_client.py` | 增加 `LLMConfig.provider` 的枚举：`openai_compat`、`gemini`、`anthropic`、`openrouter`、`ollama`。在 `_build_config_from_env()` 中：若存在 `ANTHROPIC_API_KEY` 则返回 provider=anthropic；若存在 `OPENROUTER_API_KEY` 则 openrouter；若存在 `OLLAMA_BASE_URL` 则 ollama。新增类 `AnthropicClient`、`OpenRouterClient`、`OllamaClient`，实现 `chat_completion(messages, model=...)`；Ollama 需将 messages 转为其 API 格式。 |
| `env.example` | 补充 `# ANTHROPIC_API_KEY`、`# ANTHROPIC_MODEL`、`# OPENROUTER_API_KEY`、`# OPENROUTER_MODEL`、`# OLLAMA_BASE_URL`、`# OLLAMA_MODEL`；并说明「未配置时跳过，按现有优先级选择」。 |

#### 1.3.2 优先级建议

- 与现有逻辑一致：先看 `OPENAI_API_KEY`，再 `GEMINI_API_KEY`，再 `ANTHROPIC_API_KEY`、`OPENROUTER_API_KEY`、`OLLAMA_BASE_URL`；第一个存在的生效（或通过 `LLM_PROVIDER=anthropic` 显式指定）。

#### 1.3.3 验收标准

- 仅配置 `ANTHROPIC_API_KEY` 且未配置 OpenAI/Gemini 时，请求走 Anthropic；同理 OpenRouter、Ollama。
- 现有 OpenAI 兼容、Gemini 行为不变。

#### 1.3.4 预估工时

**1～2 人天**（含 3 个新 client 与 env 解析）。

---

### 1.4 SOUL.md 身份文档

**目标**：若存在用户或项目级「身份/投资哲学」文件，则将其内容追加到每日分析 system prompt，以定制风格。

#### 1.4.1 查找顺序

1. 环境变量 `SOUL_FILE` 指定路径（若存在且可读）。
2. 项目根目录 `soul.md` 或 `identity.md`。
3. 用户目录 `~/.quant/soul.md`（若存在）。

#### 1.4.2 接口与修改点

| 文件 | 修改内容 |
|------|----------|
| `core/daily_analysis/prompts.py` | 新增 `load_soul_content() -> Optional[str]`：按上述顺序查找并读取文件，返回内容（或 None）。在 `build_messages` 中：若 `load_soul_content()` 非空，则在 system 末尾追加「## 身份与原则\n{content}」。 |
| `env.example` | 增加 `# SOUL_FILE=path/to/soul.md`（可选）。 |

#### 1.4.3 验收标准

- 在项目根放置 `soul.md` 且内容为「偏保守，优先风控」时，生成的 system 末尾包含该段。
- 未放置任何 soul 文件时，行为与当前一致。

#### 1.4.4 预估工时

**0.5 人天**。

---

## Phase 2：Prompt 模块、Financial 元工具、Agent 预留

### 2.1 结构化 Prompt 模块（工具/数据描述）

**目标**：将「数据说明」「大盘复盘说明」「技术指标说明」等拆成常量或小模块，在 `core/daily_analysis/prompts.py` 中组装，便于维护与 A/B 测试。

#### 2.1.1 目录与文件

| 类型 | 路径 | 说明 |
|------|------|------|
| 模块 | `core/daily_analysis/prompt_modules.py` | 常量或函数：`DATA_CONTEXT_DESCRIPTION`、`MARKET_REVIEW_DESCRIPTION`、`BIAS_AND_TREND_DESCRIPTION` 等 |

#### 2.1.2 修改点

- `prompts.py` 中从 `prompt_modules` 导入各片段，`build_messages` 内用 f-string 或列表 join 拼成 system；bias 阈值仍从 `config.get_bias_threshold()` 读取。

#### 2.1.3 预估工时

**0.5 人天**。

---

### 2.2 Financial 元工具（自然语言→子工具路由）

**目标**：提供 API「自然语言财务/行情查询」，后端用 LLM 解析为「标的+指标类型+时间」，再映射到现有接口（价格、复盘、新闻等）。

#### 2.2.1 接口与实现要点

- 新增路由：`POST /api/llm-analysis/natural-query`，body：`{"query": "600519 最近一周走势如何"}`。
- 实现：用 `llm_client` 调用一次 LLM，要求输出结构化 JSON，如 `{"ticker": "600519", "intent": "price_trend", "days": 7}`；再根据 intent 调用 `load_price_data`、`daily_review`、`search_news` 等，汇总后可再调一次 LLM 生成自然语言回复（或直接返回结构化数据）。

#### 2.2.2 依赖与预估

- 依赖：现有数据接口稳定；可选先做「价格+复盘」子集。  
- **2～4 人天**。

---

### 2.3 Agent 相关（Context 管理 / 工具限流 / 最终答案单独调用）

**建议**：与「是否上多步 Agent」一起规划。若上 Agent，则：

- 在 Agent 循环中维护「工具结果列表」与 token 估计；超过阈值时丢弃最旧若干条（保留最近 N 条），对应实现见《Dexter借鉴与可行性分析》第 7、8、9 节。
- Scratchpad 已预留 `tool_result`、`thinking`，可在 Agent 每步执行后追加；工具限流可复用 Dexter 的「次数+相似度」思路，在 Python 中实现 `can_call_tool` / `record_tool_call` 等价逻辑。

**预估**：与 Agent 整体开发一起，约 **2～3 人天**（在已有 Agent 骨架前提下）。

---

## 环境变量汇总（新增/变更）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SCRATCHPAD_ENABLED` | true | 是否写入分析过程 JSONL |
| `SCRATCHPAD_DIR` | data/scratchpad | Scratchpad 目录 |
| `API_RESPONSE_CACHE_ENABLED` | true | 是否启用 API 响应文件缓存 |
| `API_CACHE_DIR` | data/api_cache | API 缓存根目录 |
| `API_CACHE_TTL_PRICES` | 300 | 价格类缓存 TTL（秒） |
| `API_CACHE_TTL_MARKET_REVIEW` | 600 | 大盘复盘缓存 TTL（秒） |
| `SKILLS_ENABLED` | true | 是否加载并注入 Skills |
| `SKILLS_DIR` | core/skills | 技能目录 |
| `SOUL_FILE` | （可选） | 身份文档路径 |
| `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY` / `OLLAMA_BASE_URL` | — | 多 LLM 提供商 |

---

## 实施顺序与总工时（参考）

| 阶段 | 任务 | 工时 |
|------|------|------|
| P0 | 0.1 Scratchpad | 0.5～1 d |
| P0 | 0.2 API 响应缓存 | 1～2 d |
| P1 | 1.1 Evals | 2～3 d |
| P1 | 1.2 Skills | 1～2 d |
| P1 | 1.3 多 LLM 提供商 | 1～2 d |
| P1 | 1.4 SOUL.md | 0.5 d |
| P2 | 2.1 Prompt 模块 | 0.5 d |
| P2 | 2.2 Financial 元工具 | 2～4 d |
| P2 | 2.3 Agent 相关 | 2～3 d（与 Agent 同步） |

**P0+P1 合计约 6～11 人天**；P2 按需排期。

本方案可直接作为开发任务拆解与评审依据；实施时可根据依赖关系微调顺序（如先 0.1 再 1.2/1.4，再 0.2）。

---

## Phase 3：Agent 线引入实施方案（Dexter 风格）

在前述优化基础上，若希望进一步引入类似 Dexter 的多轮 Agent 能力，建议采用「**并行加一条 Agent 线**」的方式，而不是直接改写现有 `daily_analysis`。本节给出一套可实施的最小 MVP 方案。

### 3.1 使用场景与 API 边界

**目标**：区分「日常决策」与「深度研究」，避免现有接口被 Agent 影响性能和稳定性。

- **普通日内决策**：继续使用现有 `daily_analysis` 相关接口（如 `/api/llm-analysis/dashboard`），保持当前体验不变。  
- **深度研究模式**：针对复杂问题（公司对比、估值分析、事件影响、跨标的组合研究等）走 Agent 流程。

#### 3.1.1 新增 API 与路由

- 新增路由文件：`api/routers/agent.py`
  - `POST /api/agent/research`
    - 请求体：`{"query": "你的研究问题", "model": null}`  
      - `query`: 自然语言问题；  
      - `model`: 可选，显式指定本次使用的 LLM 模型名，留空使用默认。
    - 返回结构（示例）：  
      - `answer`: 最终自然语言结论（Markdown 或纯文本）；  
      - `tool_calls`: Agent 过程中调用的工具列表（名称、参数、摘要）；  
      - `scratchpad_path`: 本次会话对应的 scratchpad 文件路径；  
      - `iterations`: 实际迭代轮数；  
      - `token_usage`: 可选，token 统计信息。
- 注意：**现有** `/api/llm-analysis/*` 路由保持不变，仅在新路由中引入 Agent。

---

### 3.2 工具接口抽象（Tools）

**目标**：把目前分散的能力抽象为可被 Agent 调用的「工具」，每个工具都有清晰的入参/出参与自然语言描述，类似 Dexter 的 `tools` 体系。

#### 3.2.1 目录与文件

| 类型 | 路径 | 说明 |
|------|------|------|
| 模块 | `core/agent/tools.py` | 定义 Tool 抽象基类与具体工具实现 |
| 配置 | `core/agent/__init__.py` | 暴露工具注册函数（如 `get_default_tools()`） |

#### 3.2.2 抽象基类设计

```python
# core/agent/tools.py（示意）
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class ToolResult:
    name: str
    args: Dict[str, Any]
    data: Dict[str, Any]

class BaseTool:
    name: str
    description: str

    def run(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError
```

#### 3.2.3 建议的首批工具

- **PriceTool**
  - 入参：`ticker: str`, `days: int`  
  - 实现：封装当前 `core.data_service.load_price_data` 与基础指标计算逻辑（或直接复用 `builder` 中的部分）。  
  - 返回：最近 N 日价格序列、基础指标（MA、涨跌幅等）。
- **MarketReviewTool**
  - 入参：`market: str` (`"cn"|"us"|"both"`)  
  - 实现：调用 `core.market_review.daily_review`。  
  - 返回：大盘指数、涨跌概况、板块信息、北向资金等。
- **NewsSearchTool**
  - 入参：`ticker: str`, `days: int`  
  - 实现：将当前 `builder.build_analysis_input` 中的新闻搜索逻辑抽出，放到该工具中。  
  - 返回：标题、链接、摘要、来源列表。
- **DailyDecisionTool**
  - 入参：`ticker: str`, `market: str`  
  - 实现：直接调用现有 `run_daily_analysis(tickers=[ticker], market=market)`，作为「高阶决策工具」。  
  - 返回：与现有 dashboard 相同的决策结构，用于 Agent 在多步推理中调用。

> 后续可按需增加：`BacktestTool`（封装 `backtest_ticker`）、`FundamentalsTool`（财报/估值数据）等。

#### 3.2.4 工具自然语言描述

每个工具应提供一段简短说明，用于注入 Agent system prompt（类似 Dexter 的 tool descriptions）：

- 何时使用：典型场景、问题类型；
- 何时不应使用：如「PriceTool 不适合读取大盘复盘，请用 MarketReviewTool」；
- 返回数据大致结构：帮助 LLM 更好消费工具结果。

---

### 3.3 Agent 核心（轻量循环）

**目标**：实现一个最小可用的 Agent 循环，支持多轮「思考 → 调用工具 → 写入 scratchpad → 继续/结束」，架构风格对齐 Dexter 的 `Agent`，但先从轻量版本开始。

#### 3.3.1 目录与文件

| 类型 | 路径 | 说明 |
|------|------|------|
| Agent 实现 | `core/agent/agent.py` | 定义 `AgentState` 与 `run_agent` 主循环 |
| Runner 封装 | `core/agent/runner.py` | 提供对外的 `run_agent(query, model)` 接口 |

#### 3.3.2 AgentState 建议字段

- `query`: 用户原始问题；
- `iteration`: 当前迭代次数；
- `max_iterations`: 最大迭代次数（例如 3～6）；
- `tools`: 可用工具列表（`BaseTool` 实例）；
- `scratchpad_path`: 本次会话对应的 scratchpad 文件路径；
- `messages`: 与 LLM 的对话历史（可选）；
- `tool_results`: 已获得的工具结果摘要列表。

#### 3.3.3 单轮迭代流程（伪代码）

```python
while state.iteration < state.max_iterations:
    prompt = build_iteration_prompt(state)  # 包含 query、已有工具结果、技能列表、SOUL等
    llm_reply = call_llm(prompt)            # 返回「思考 + 工具调用计划」

    plan = parse_tool_plan(llm_reply)       # 解析出要调用哪些工具及参数
    if not plan.tools_to_call:
        break  # LLM 认为可以直接给出最终答案

    for tool_call in plan.tools_to_call:
        result = tool_registry[tool_call.name].run(**tool_call.args)
        write_tool_result_to_scratchpad(result)
        state.tool_results.append(result)

    state.iteration += 1
```

迭代结束后，再用单独的 `build_final_answer_prompt` 拼接「原始问题 + 整体工具结果」，调用一次 LLM 生成最终答案。

#### 3.3.4 与现有 scratchpad 的集成

- 在 `core/scratchpad.py` 基础上，增加/约定新的 `type` 值：
  - `tool_plan`: LLM 给出的本轮工具调用计划；
  - `tool_result`: 工具调用结果（已存在，可扩展字段）；  
  - `thinking`: LLM 的中间思考片段（可用于调试）。
- Agent 每一轮：
  - 在规划阶段写入一条 `tool_plan`；
  - 工具执行完写入一条 `tool_result`；
  - 若 LLM 输出了可读的「思考」段落，则写入 `thinking`。

---

### 3.4 Agent 专用 Prompt（System + Iteration 模板）

**目标**：为 Agent 定制 prompt，包含工具说明、技能与身份文档，以及停止条件等规则，使结构接近 Dexter 的 `buildSystemPrompt + buildIterationPrompt`。

#### 3.4.1 目录与文件

| 类型 | 路径 | 说明 |
|------|------|------|
| Prompt 模块 | `core/agent/prompts.py` | system prompt + iteration/final-answer prompt 构造函数 |

#### 3.4.2 System Prompt 要点

- 「你是谁」：复用 SOUL 文档，说明投资风格（保守/激进等）。  
- 「可用工具」：按工具列表生成类似：
  - 工具名 + 简要描述；
  - 何时用 / 何时不用；
  - 注意事项（如成本、时效性、返回结构）。
- 「技能」：复用 `core/skills` 中的技能元数据，类似当前 `daily_analysis` 的实现。  
- 「行为规范」：
  - 避免无限循环和无意义的工具调用；  
  - 优先利用已有工具结果，尽量减少重复请求；  
  - 在最终回答中明确引用数据来源和关键假设。

#### 3.4.3 Iteration / Final Answer Prompt

- `build_iteration_prompt(state)`：
  - 包含：原始 query、简要工具结果列表（可只保留摘要）、当前迭代次数、工具使用情况（次数等）。  
  - 引导 LLM：先思考，再决定是否调用新工具或直接尝试回答。
- `build_final_answer_prompt(state)`：
  - 包含：原始 query、所有重要工具结果（可从 scratchpad 重建）、必要的上下文说明；  
  - 要求 LLM 用结构化摘要/列表形式回答，并标注不确定之处。

---

### 3.5 API 集成：Agent Runner 与路由

**目标**：通过一个清晰的 Runner 封装 Agent 调用逻辑，再由新路由对外暴露。

#### 3.5.1 Runner 封装

- 文件：`core/agent/runner.py`
  - 函数：`run_agent(query: str, model: Optional[str] = None) -> Dict[str, Any]`
    - 负责：
      - 创建 `AgentState`；
      - 初始化工具列表（根据场景或配置选择）；  
      - 调用 Agent 循环，捕获异常并写入 scratchpad；  
      - 统一返回结构（answer、tool_calls、scratchpad_path、iterations、token_usage 等）。

#### 3.5.2 API 路由

- 文件：`api/routers/agent.py`
  - `POST /api/agent/research`：
    - Body：`{"query": "...", "model": null}`；  
    - 内部调用 `run_agent`，直接返回其结果；
    - 可选增加简单 RBAC（只允许内网/管理员使用）。

---

## 当前项目的硬瓶颈与 Agent 引入注意事项

结合现有实现与 Dexter 经验，引入 Agent 时需重点关注以下几点：

### 1. 数据源速度与稳定性

- Agent 模式下，LLM 可能多次调用工具（多次访问 akshare/yfinance/新闻搜索等），**慢/不稳定的数据源会被放大**：
  - 你已经有 `MultiLevelCache`、`api_response_cache` 与本地 `data_store`，但仍需：  
    - 为每个工具设置合理的 timeout 与重试策略；  
    - 所有错误都转化为「结构化错误对象」写入 scratchpad（例如 `{error: ..., source: ...}`），而不是直接抛异常中断整个 Agent。

### 2. 成本与延迟

- 多轮 Agent = 多次 LLM 调用 + 多次数据请求，相比单轮 `daily_analysis` 成本和响应时间都会显著增加。
- 建议：
  - 在 AgentState 中限制 `max_iterations`、每个工具的最大调用次数；  
  - 只在用户显式点击「深度研究」或访问 `/api/agent/research` 时才使用 Agent，其余路径继续走现有逻辑。

### 3. 可调试性与可观测性

- 优势：你已具备 scratchpad、Evals 与日志体系，是 Agent 调试的良好基础。
- 建议：
  - 在 scratchpad 中为 Agent 步骤使用清晰的 `type`：`planning` / `tool_plan` / `tool_result` / `thinking` / `final_answer`；  
  - 在 Evals 中新增一条针对 Agent 的评估流程（与当前 daily_analysis 对比），便于量化「Agent 是否真的更好」。

### 4. 与现有 daily_analysis 的边界

- 风险：若直接把 `daily_analysis` 改成 Agent 实现，容易导致「原本简单快速的决策接口变慢、变不稳定」。
- 建议：
  - 保留 `daily_analysis` 作为 **高层工具**（即上文的 `DailyDecisionTool`），Agent 在需要时去调用它，而不是反过来；  
  - 在用户层面维持两个不同入口：  
    - 「普通决策」：走现有 dashboard/daily_analysis；  
    - 「Agent 研究」：走 `/api/agent/research` 与独立的前端页面。

---

以上 Phase 3 方案可以在 P0/P1/P2 完成后单独立项推进：  
- 首先实现最小工具集（PriceTool、MarketReviewTool、NewsSearchTool、DailyDecisionTool）；  
- 然后搭建轻量 Agent 核心与 Runner；  
- 最后通过 `/api/agent/research` 逐步灰度放量，并用 Evals/日志验证 Agent 带来的价值与边际成本。
