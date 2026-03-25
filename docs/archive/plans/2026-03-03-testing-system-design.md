# 测试体系设计方案

> 设计日期：2026-03-03
> 版本：v1.3.0
> 优先级：P0 (Critical)

## 1. 设计目标

建立完整的测试体系，覆盖单元测试、集成测试、性能测试和 E2E 测试，确保代码质量和系统稳定性。

```
┌─────────────────────────────────────────────────────────┐
│                    测试金字塔                            │
├─────────────────────────────────────────────────────────┤
│  E2E Tests    │  5-10%  │ 全面用户流程验证               │
│  Integration  │  20-30% │  API/模块间交互验证            │
│  Unit Tests   │  60-75% │  核心逻辑单元验证              │
└─────────────────────────────────────────────────────────┘
```

## 2. 测试类型与覆盖范围

### 2.1 单元测试 (Unit Tests)

**目标**：覆盖 >85% 代码行

| 模块 | 测试重点 | 覆盖率目标 |
|------|----------|-----------|
| `core/data_service.py` | 数据获取、缓存、异常处理 | >90% |
| `core/advanced_forecasting.py` | 模型训练、预测、特征工程 | >85% |
| `core/backtest_engine.py` | 回测逻辑、订单执行、指标计算 | >90% |
| `core/analysis/performance.py` | 绩效指标计算 | >95% |
| `core/risk_monitor.py` | 风控规则、预警逻辑 | >85% |
| `core/trading_engine.py` | 订单管理、仓位控制 | >85% |

**测试框架**：
```python
# pytest + pytest-asyncio + pytest-cov
pytest tests/unit/ -v --cov=core --cov-report=html
```

### 2.2 集成测试 (Integration Tests)

**目标**：覆盖核心业务流程

| 场景 | 测试点 | 优先级 | 文件 |
|------|--------|--------|------|
| 完整回测流程 | 数据加载 → 策略执行 → 指标计算 | P0 | `test_backtest_api.py` |
| 模型训练流程 | 数据准备 → 训练 → 评估 → 注册 | P0 | `test_ai_pipeline.py` |
| 多策略回测 | 策略组合 → 权重分配 → 对比分析 | P0 | `test_backtest_api.py` |
| API 端点 | 所有路由的请求/响应验证 | P0 | `test_api_forecasting.py` |
| 数据缓存 | Redis/本地缓存命中率 | P1 | `test_data_pipeline.py` |

**测试框架**：
```python
# 运行所有集成测试
pytest tests/integration/ -v

# 运行特定测试文件
pytest tests/integration/test_backtest_api.py -v
```

### 2.3 性能测试 (Performance Tests)

**目标**：确保关键操作在可接受时间内完成

| 测试项 | 阈值 | 工具 | 文件 |
|--------|------|------|------|
| 单次回测 (<1000 stocks) | <30s | pytest-benchmark | `test_backtest_benchmark.py` |
| 模型训练 (60天数据) | <60s | pytest-benchmark | `test_forecasting_benchmark.py` |
| API 响应时间 (p95) | <200ms | locust | - |
| 并发用户支持 | >100 | locust | - |

**测试框架**：
```python
# 安装 pytest-benchmark
pip install pytest-benchmark

# 运行性能基准测试
pytest tests/performance/ -v --benchmark-only

# 运行特定性能测试
pytest tests/performance/test_backtest_benchmark.py -v
```

### 2.4 E2E 测试

**目标**：覆盖核心用户流程

| 用户流程 | 测试点 | 工具 | 文件 |
|----------|--------|------|------|
| 用户注册/登录 | 完整流程 | Playwright | `test_auth.py` |
| 查看市场数据 | 数据加载、图表渲染 | Playwright | `test_market.py` |
| 运行回测 | 配置 → 执行 → 结果查看 | Playwright | `test_backtest.py` |
| 策略对比 | 多策略运行 → 对比分析 | Playwright | `test_strategy_comparison.py` |

**测试框架**：
```python
# 安装 Playwright
pip install pytest-playwright
playwright install

# 运行 E2E 测试
pytest tests/e2e/ -v -m e2e
```

## 3. 测试文件结构

```
tests/
├── __init__.py
├── conftest.py              # pytest 共享 fixture
├── fixtures/                # 测试数据/fixtures
│   ├── prices.csv
│   ├── backtest_trades.json
│   └── model_predictions.json
├── unit/                    # 单元测试
│   ├── test_data_service.py
│   ├── test_forecasting.py
│   ├── test_backtest_engine.py
│   ├── test_performance.py
│   ├── test_risk_monitor.py
│   └── test_trading_engine.py
├── integration/             # 集成测试
│   ├── test_api.py
│   ├── test_backtest_flow.py
│   ├── test_training_flow.py
│   └── test_cache.py
├── performance/             # 性能测试
│   ├── test_backtest_benchmark.py
│   ├── test_api_performance.py
│   └── conftest.py
└── e2e/                     # E2E 测试
    ├── test_auth.py
    ├── test_market.py
    ├── test_backtest.py
    ├── test_strategy_comparison.py
    └── conftest.py
```

## 4. 测试覆盖关键代码

### 4.1 回测引擎测试 (`test_backtest_engine.py`)

```python
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

class TestBacktestEngine:
    """回测引擎单元测试"""

    @pytest.fixture
    def sample_price_data(self) -> pd.DataFrame:
        """生成示例价格数据"""
        dates = pd.date_range('2024-01-01', periods=100, freq='B')
        return pd.DataFrame({
            'open': np.random.randn(100).cumsum() + 100,
            'high': np.random.randn(100).cumsum() + 102,
            'low': np.random.randn(100).cumsum() + 98,
            'close': np.random.randn(100).cumsum() + 100,
            'volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)

    def test_clean_starting_cash(self, sample_price_data):
        """验证起始资金正确性"""
        from core.backtest_engine import BacktestEngine
        engine = BacktestEngine(cash=100000)
        assert engine.broker.cash == 100000

    def test_buy_position_creation(self, sample_price_data):
        """验证买入创建仓位"""
        pass

    def test_sell_position_closure(self, sample_price_data):
        """验证卖出关闭仓位"""
        pass

    def test_metrics_calculation(self, sample_price_data):
        """验证指标计算正确性"""
        pass
```

### 4.2 数据服务测试 (`test_data_service.py`)

```python
class TestDataService:
    """数据服务单元测试"""

    @pytest.mark.asyncio
    async def test_fetch_ashare_prices(self):
        """验证 A 股价格数据获取"""
        pass

    @pytest.mark.asyncio
    async def test_fetch_us_prices(self):
        """验证 US 股价格数据获取"""
        pass

    def test_cache_hit(self):
        """验证缓存命中"""
        pass

    def test_fallback_on_error(self):
        """验证错误时的降级机制"""
        pass
```

### 4.3 API 集成测试 (`test_api.py`)

```python
class TestBacktestAPI:
    """回测 API 集成测试"""

    async def test_run_single_strategy(self, client):
        """POST /api/backtest/run - 单策略回测"""
        pass

    async def test_run_multi_strategy(self, client):
        """POST /api/backtest/run-multi - 多策略回测"""
        pass

    async def test_optimize_parameters(self, client):
        """POST /api/backtest/optimize - 参数优化"""
        pass

    async def test_benchmark_comparison(self, client):
        """POST /api/backtest/benchmark - 基准对比"""
        pass
```

## 5. CI/CD 集成

### 5.1 GitHub Actions Workflow

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run unit tests with coverage
        run: |
          pytest tests/unit/ -v --cov=core --cov-report=xml

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

      - name: Run integration tests
        run: pytest tests/integration/ -v -m "not e2e"

      - name: Check coverage threshold
        run: |
          coverage report --fail-under=85
```

### 5.2 pre-commit Hooks

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb', '1000']

  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=120']
```

## 6. 测试数据管理

### 6.1 固定测试数据 (/fixtures)

```
tests/fixtures/
├── prices_600519.csv           # 贵州茅台示例价格数据
├── prices_000001.csv           # 平安银行示例价格数据
├── prices_000300.csv           # 沪深300指数
├── backtest_trades_example.json
├── model_predictions_example.json
└── competition_data.json
```

### 6.2 动态生成数据

```python
# tests/conftest.py
import pytest
import pandas as pd
import numpy as np

@pytest.fixture
def random_price_data():
    """生成随机价格数据用于测试"""
    dates = pd.date_range('2024-01-01', periods=252, freq='B')
    prices = 100 + np.cumsum(np.random.randn(252))
    return pd.DataFrame({
        'open': prices + np.random.randn(252) * 0.5,
        'high': prices + np.random.randn(252) * 0.5,
        'low': prices - np.random.randn(252) * 0.5,
        'close': prices + np.random.randn(252) * 0.5,
        'volume': np.random.randint(1e6, 1e7, 252)
    }, index=dates)
```

## 7. 测试覆盖率目标

| 模块 | 行覆盖率 | 分支覆盖率 | 目标完成日期 |
|------|----------|------------|-------------|
| `core/data_service.py` | 90% | 85% | v1.3.0 |
| `core/advanced_forecasting.py` | 85% | 80% | v1.3.0 |
| `core/backtest_engine.py` | 90% | 85% | v1.3.0 |
| `core/risk_monitor.py` | 85% | 80% | v1.3.0 |
| `core/trading_engine.py` | 85% | 80% | v1.3.0 |
| **整体** | **85%** | **80%** | **v1.3.0** |

## 8. 测试优先级矩阵

| 优先级 | 描述 | 测试类型 | 示例 |
|--------|------|----------|------|
| P0 | 核心功能，数据正确性 | 单元 + 集成 | 回测逻辑、风控规则 |
| P1 | 重要流程，稳定性 | 单元 + 集成 | API 端点、缓存机制 |
| P2 | 用户体验，边界情况 | 单元 + E2E | UI 交互、错误提示 |
| P3 | 罕见场景 | 单元 | 异常数据处理 |

## 9. 实施计划

### Phase 1: Unit Test Foundation (v1.3.0 Alpha)
- [ ] 创建测试框架和基础Fixture
- [ ] 覆盖核心工具函数 (>90%)
- [ ] 覆盖数据清洗逻辑 (>85%)

### Phase 2: Core Module Coverage (v1.3.0 Beta)
- [ ] 覆盖回测引擎 (>90%)
- [ ] 覆盖 forecasting 模块 (>85%)
- [ ] 覆盖 risk_monitor 模块 (>85%)

### Phase 3: Integration & E2E (v1.3.0 RC)
- [ ] 完整回测流程测试
- [ ] API 集成测试
- [ ] E2E 用户流程测试

### Phase 4: CI/CD Integration (v1.3.0)
- [ ] GitHub Actions 配置
- [ ] Codecov 集成
- [ ] 覆盖率阈值检查

## 10. 成功指标

- [ ] 单元测试 >85% 覆盖率
- [ ] 所有 P0/P1 Bug 有对应测试
- [ ] CI/CD 自动运行测试
- [ ] 每次 PR 至少新增一个测试
- [ ] 测试运行时间 <10 分钟

---
*设计作者：Claude Code*
*下次评审：v1.3.0 发布前*
