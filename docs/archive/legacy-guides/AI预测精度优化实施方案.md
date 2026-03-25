## AI 预测精度优化实施方案

### 1. 背景与目标

- **背景**：当前系统主要依赖 XGBoost / Prophet 等模型进行净值/价格预测，已具备较好的稳定性，但在部分标的和市场环境下仍存在精度与鲁棒性不足的问题。
- **目标**：在不显著增加资源开销、尽量兼容现有架构的前提下，将预测误差（如 MAPE、RMSE）整体降低 10–20%，并提升不同市场环境下的稳健性。

---

### 2. 总体实施路径

- **阶段一（本月内）**：优先落地数据质量与目标变量优化、时间序列交叉验证，配合低成本快速优化项。
- **阶段二（1–2 个月）**：引入超参数自动调优、集成策略优化。
- **阶段三（2–3 个月）**：完成多源数据接入及市场状态自适应路由，持续迭代。

---

### 3. 方案一：数据质量与多源融合（优先级 ★★★★★）

#### 3.1 内容概述

| 措施             | 说明                                                                 | 难度 |
| ---------------- | -------------------------------------------------------------------- | ---- |
| 接入成交量数据   | 当前仅使用收盘价，缺少量价关系特征。加入成交量后可计算 OBV、VWAP、量比等 | 低   |
| 融合多时间粒度   | 同时用日线 + 周线特征训练，捕捉不同频率信号                         | 中   |
| 数据清洗增强     | 对停牌、除权除息、异常值进行更严格处理                               | 低   |

- **预期收益**：整体精度提升约 **10–20%**。

#### 3.2 实施步骤

1. **成交量数据接入**
   - 在 `core/data_service.py` 中扩展 `load_price_data`，支持返回 `close` + `volume`（或从外部数据源直接拉取 OHLCV）。
   - 在 `FeatureEngineer` 中新增基于成交量的特征（OBV、量比、成交量均线等），并通过 `use_enhanced_features` 开关控制是否启用。
2. **多时间粒度融合**
   - 为关键标的构建周线序列（按周聚合日线 OHLCV）。
   - 设计 “多粒度特征拼接” 方案：如在 XGBoost/LightGBM 特征中加入周线动量、周线波动率等。
3. **数据清洗增强**
   - 针对停牌日、极端缺失日进行剔除或前向填充。
   - 在除权除息日进行价格复权处理，保证序列平滑。
   - 对异常值（如单日波动 > 30%）进行截断或 Winsorize。

---

### 4. 方案二：目标变量优化（优先级 ★★★★★）

#### 4.1 内容概述

- 当前目标：`pct_change(horizon)`，即收盘到收盘的简单收益率。
- 优化方向：
  - 改用对数收益率 \( \log(P_{t+h} / P_t) \) 更符合正态分布假设。
  - 使用 **多步滚动预测** 替代直接预测 horizon 天后价格。
  - 采用 **分类 + 回归双任务**：先预测方向（涨 / 跌 / 盘整），再预测幅度。

- **预期收益**：精度提升约 **5–15%**，同时提高稳定性。

#### 4.2 实施步骤

1. **目标定义调整**
   - 在 `FeatureEngineer.create_target` 中增加对数收益率选项（可通过参数控制），例如：
     - `target = log_price.shift(-horizon) - log_price`
2. **多步滚动预测**
   - 对 XGBoost / LightGBM / RandomForest 预测逻辑进行改造：
     - 模型先预测 1 日收益率；
     - 将预测值迭代叠加，滚动得到 3/5/7/30 日的路径。
3. **方向 + 幅度双任务（可选进阶）**
   - 在训练管线中增加一个方向分类器（label = sign(未来收益)）。
   - 使用方向预测为回归模型提供调整权重（如对方向错误的样本赋予更大的惩罚）。

---

### 5. 方案三：超参数自动调优（优先级 ★★★★）

#### 5.1 内容概述

- 问题：当前 XGBoost 使用固定参数 `(n_estimators=100, max_depth=6, learning_rate=0.1)`，对不同标的和周期不够自适应。
- 方案：引入 **Optuna** 进行贝叶斯超参数搜索，对关键标的定期做轻量级调参。

- **预期收益**：精度提升约 **10–20%**，对内存影响较小（Optuna 本身较轻量）。

#### 5.2 实施步骤

1. **引入依赖**
   - 在 `requirements.txt` 中加入 `optuna`（如 `optuna>=3.0.0`）。
2. **定义搜索目标函数**

```python
import optuna

def objective(trial):
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 50, 500),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
    }
    # 使用时间序列交叉验证评估
    # return -validation_metric  # 例如 -MAPE 或 -RMSE
```

3. **与训练流水线集成**
   - 在 `core/training_pipeline.py` 中增加调参模式：对重点标的定期（如每周）进行 N 轮搜索（如 30–50 trial）。
   - 将最优参数写入 `models/registry.json`，供后续训练加载。

---

### 6. 方案四：时间序列交叉验证（优先级 ★★★★）

#### 6.1 内容概述

- 问题：若不使用严格的时间序列交叉验证，容易产生「未来信息泄露」，对回测和线上效果均有影响。
- 方案：使用 `sklearn.model_selection.TimeSeriesSplit` 扩展窗口法，并在最终模型上执行 Walk-Forward 验证。

- **预期收益**：有效减少过拟合，实际线上误差可降低 **5–10%**。

#### 6.2 实施步骤

1. **引入 TimeSeriesSplit**
   - 在 `XGBoostForecaster.fit` / `LightGBMForecaster.fit` / `RandomForestForecaster.fit` 中，增加基于时间窗口的 CV 流程，用于：
     - 选择超参数；
     - 估计模型泛化误差。
2. **Walk-Forward 验证框架**
   - 在 `training_pipeline.py` 中增加统一的 Walk-Forward 评估函数：
     - 例如每次使用过去 N 天训练，预测未来 M 天，滚动滑窗。
   - 将评估指标记录到日志和 `models/registry.json` 中，用于模型选择和回滚。

---

### 7. 方案五：集成策略优化（优先级 ★★★）

#### 7.1 内容概述

- 当前集成模型仅使用简单加权平均。
- 改进方向：
  - **Stacking**：使用二层模型（如 Ridge 回归、轻量 XGBoost）学习各子模型的最优组合权重。
  - **动态权重**：根据各模型近 N 日的预测误差动态调整权重。
  - **多样性约束**：保证子模型在结构与特征上的多样性，例如：
    - Prophet：捕捉季节性与长期趋势；
    - XGBoost：捕捉非线性因子；
    - ARIMA：捕捉线性趋势和平稳性。

#### 7.2 实施步骤

1. **完善 `EnsembleForecaster`**
   - 增加训练期对各模型误差的记录接口。
   - 增加基于误差倒数/Sharpe 等指标的权重更新逻辑。
2. **Stacking 二层模型**
   - 将各子模型输出作为特征，训练轻量回归模型得到最终预测。
   - 在 `training_pipeline.py` 中增加 “集成训练” 模式，对比单模型与集成模型表现。

---

### 8. 方案六：市场状态自适应（优先级 ★★★）

#### 8.1 内容概述

- 不同市场环境下最优模型不同：
  - **趋势行情**：动量策略 + XGBoost 表现更好；
  - **震荡行情**：均值回归 + ARIMA 更适合；
  - **高波动**：应降低预测周期、增大置信区间。
- 方案：通过 **市场状态识别 + 模型路由** 提升稳健性。

#### 8.2 实施步骤

1. **市场状态识别**
   - 使用简单指标（如波动率、ADX、均值回归 Z 分数）进行规则分类：
     - 低波动 & 弱趋势 → 震荡；
     - 高波动 & 强趋势 → 趋势；
     - 其余 → 过渡状态。
   - 或引入隐马尔可夫模型（HMM）学习隐含市场状态。
2. **模型路由策略**
   - 在 `quick_predict` / `run_forecast` 前增加 “状态 → 模型/参数” 路由表：
     - 趋势：优先 XGBoost / LightGBM，拉长 lookback；
     - 震荡：优先 ARIMA / 均值回归类特征；
     - 高波动：缩短 horizon，调大置信区间系数。

---

### 9. 方案七：低成本可实施的快速提升（立即可做）

#### 9.1 内容概述

| 改进项                          | 代码位置                          | 改动量 |
| ------------------------------- | --------------------------------- | ------ |
| 启用增强特征 `use_enhanced_features=True` | `XGBoostForecaster.__init__`      | 1 行   |
| 增加 early stopping 防止过拟合 | `XGBoostForecaster.fit` 中加入 `eval_set` | ~5 行  |
| 预测时加入历史回测评分         | `quick_predict` 返回中加入 `accuracy_score` 等指标 | ~10 行 |
| 定期自动重训练                 | `training_pipeline.py` 的 daemon 定时触发 | 已有框架 |

#### 9.2 建议优先顺序

1. 在所有树模型中统一 **开启增强特征**（现有实现已增强 FeatureEngineer，可直接利用）。
2. 在训练阶段加入 **early stopping**，并记录最佳迭代轮数。
3. 在预测 API 中返回 **最近回测评分**（如过去 30/90 日的 MAPE），前端可用于展示模型置信度。
4. 使用现有 daemon 机制，针对生产标的做 **夜间批量重训练**，保持模型与数据同步。

---

### 10. 里程碑与验收

- **阶段一（基础优化）**
  - 完成：数据清洗增强、目标变量优化、TimeSeriesSplit + Walk-Forward 验证。
  - 验收：关键标的近 6 个月回测 MAPE 降低 ≥ 10%，线上误差同步下降。
- **阶段二（调参与集成）**
  - 完成：Optuna 调参、集成策略优化（静态 + 动态权重 / Stacking）。
  - 验收：对照单模型，集成模型在多数标的上取得更低误差，且最大回撤不恶化。
- **阶段三（自适应与多源）**
  - 完成：成交量与多时间粒度接入、市场状态自适应路由。
  - 验收：在不同波动环境下，误差波动收窄，极端行情中的预测表现更稳健。

本方案可以按阶段逐步实施，优先落地低成本、高收益的改动（方案一、二、四与七），同时预留接口支持后续更复杂的集成与自适应策略。

---

### 11. 实施记录（已落地项）

| 方案 | 状态 | 说明 |
|------|------|------|
| 方案一 | 已实施 | `core/data_service.py` 新增 `_clean_price_dataframe()`：去重、前向填充限制 5 天、单日收益率 Winsorize ±30%，并在 `load_price_data()` 返回前统一调用。成交量与多时间粒度预留接口，可按需扩展。 |
| 方案二 | 已实施 | `FeatureEngineer.create_target()` 增加 `use_log_return` 参数；XGBoost/LightGBM/RandomForest 支持 `use_log_return`，预测时按 exp(r) 换算价格。多步滚动预测已由树模型「预测 1 日收益再迭代」实现。 |
| 方案三 | 已实施 | `requirements.txt` 增加 `optuna>=3.0.0`；`core/advanced_forecasting.py` 新增 `run_optuna_xgboost_tuning()`；`ModelManager.train_xgboost()` 支持 `**kwargs` 透传超参；`core/training_pipeline.py` 新增 `run_hyperparameter_tuning(ticker, model_type, n_trials)`。 |
| 方案四 | 已实施 | 训练成功后 `TrainingPipeline.train_model()` 调用 `evaluate_model()` 做 Walk-Forward 验证，并将结果写入 `registry.update_model_metrics()`。 |
| 方案五 | 已实施 | `EnsembleForecaster.fit(price_series, holdout_size=20)`：在最后 20 天做留出验证，按各模型 MAPE 倒数更新动态权重；`run_forecast` 中集成调用时传入 `holdout_size=20`。 |
| 方案六 | 已实施 | `core/advanced_forecasting.py` 新增 `detect_market_state(price_series)`（规则：波动率/趋势强度 → trend / range / high_volatility）；`run_forecast` 与 `quick_predict` 支持 `model_type="auto"` 时按状态路由（趋势/高波动→XGBoost，震荡→ARIMA，高波动缩短 horizon）。前端模型选择增加「自动（按市场状态）」选项。 |
| 方案七 | 已实施 | 树模型默认 `use_enhanced_features=True`；XGBoost 训练时支持 `eval_set` + `early_stopping_rounds`；`quick_predict` 在存在注册表评估指标时返回 `{ prediction, metrics }`；GET `/forecasting/predict/{ticker}` 响应中增加可选 `metrics` 字段。 |


