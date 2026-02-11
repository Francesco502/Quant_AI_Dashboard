## `data/` 目录结构规划（本地数据仓库）

`data/` 用于长期保存本地行情、账户、模型、信号等数据，是整个系统的“本地数据仓库”根目录。

### 顶层结构

- `data/prices/`：行情价格数据（收盘价 / K 线等）
- `data/accounts/`：账户与持仓相关数据（模拟盘 / 实盘）
- `data/models/`：训练好的模型与相关元数据
- `data/signals/`：选股结果、交易信号、回测中间结果等
- `data/configs/`：运行时导出的策略配置快照（可选）
- `data/backup/`：重要数据的简单备份归档（可选）

> 说明：目录会在程序运行或脚本执行过程中按需自动创建，不需要手工提前建好全部子目录。

---

### 1. `data/prices/` —— 本地行情数据仓库

- **用途**：统一存放各市场的价格时间序列（通常为日线收盘价或 K 线）。
- **典型路径**（由 `core.data_store` 读写）：
  - `data/prices/A股/600519.SS.parquet`
  - `data/prices/美股/AAPL.parquet`
  - `data/prices/港股/0700.HK.parquet`
- **特点**：
  - 由数据更新任务（如 `core.daemon` 或 `core.ohlcv_fetcher`）写入；
  - 是多数分析与策略模块的统一数据源。

---

### 2. `data/accounts/` —— 账户与持仓数据

- **用途**：存放模拟账户 / 实盘账户的资金、持仓、交易记录等。
- **当前约定**：
  - 后台守护进程模拟账户：
    - `data/accounts/paper_account_daemon.json`
  - 前端（Web 会话）模拟账户（建议后续也归入本目录）：
    - 例如：`data/accounts/paper_account_web.json`
- **特点**：
  - 以 JSON 为主，便于手动检查与简单备份；
  - 后续可以根据需要扩展为 SQLite / Parquet。

---

### 3. `data/models/` —— 训练好的模型与元数据

- **用途**：集中存放各类预测模型（XGBoost、LSTM、Prophet 等）以及相关配置。
- **推荐结构**：
  - `data/models/AAPL/xgboost_v1.pkl`
  - `data/models/AAPL/metadata.json`
  - `data/models/index/ensemble_config.json`
- **特点**：
  - 训练任务/后台服务负责写入；
  - Dashboard 只负责加载与在线推理。

---

### 4. `data/signals/` —— 交易信号与选股结果

- **用途**：保存策略产生的信号序列、选股列表、回测中间结果等。
- **示例**：
  - `data/signals/daily_signals_2025-01-01.parquet`
  - `data/signals/z_selectors/2025-01-01.csv`
  - `data/signals/backtest/ma_crossover_AAPL_2020-2024.parquet`
- **特点**：
  - 便于后续做统计分析与审计；
  - 可与 `data/models/`、`data/accounts/` 结合，实现端到端流水线追踪。

---

### 5. `data/configs/` —— 策略与运行配置快照（可选）

- **用途**：定期导出当前策略参数、风控设置等，作为“版本快照”。
- **示例**：
  - `data/configs/strategy_config_2025-01-01.json`
  - `data/configs/risk_limits_v3.json`
- **特点**：
  - 便于回溯“当时策略是如何配置的”；
  - 也可以结合 Git 存在仓库外部。

---

### 6. `data/backup/` —— 重要数据备份（可选）

- **用途**：手工或定时任务，将关键数据（账户、模型、信号等）打包归档。
- **示例**：
  - `data/backup/2025-01-01_accounts.tar.gz`
  - `data/backup/2025-01-01_models.tar.gz`
- **建议**：
  - 在服务器上配合 `cron` 或外部备份系统使用；
  - 可按日期 / 周期清理旧备份。

---

### 与现有代码的对应关系（当前状态）

- `core.data_store`：根目录使用 `data/`，行情数据集中在 `data/prices/`。
- `core.daemon`：后台模拟账户使用 `data/accounts/paper_account_daemon.json`。
- Docker 挂载：`./data:/app/data`，确保容器重启后数据不会丢失。


