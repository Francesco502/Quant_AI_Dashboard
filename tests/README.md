# 测试体系文档

本目录包含完整的测试体系，包括单元测试、集成测试和性能测试。

## 📁 测试目录结构

```
tests/
├── conftest.py              # pytest配置和共享fixtures
├── pytest.ini              # pytest配置文件
├── unit/                    # 单元测试
│   ├── test_risk_analysis.py
│   ├── test_data_service.py
│   ├── test_trading_engine.py
│   └── test_strategy_engine.py
├── integration/             # 集成测试
│   ├── test_trading_flow.py
│   └── test_data_pipeline.py
├── performance/             # 性能测试
│   ├── test_data_loading.py
│   └── test_backtest_performance.py
└── test_*.py                # 其他模块测试（风险管理、订单管理等）
```

## 🚀 运行测试

### 安装依赖

```bash
pip install pytest pytest-cov pytest-mock pytest-asyncio
```

### 运行所有测试

```bash
# 在项目根目录运行
pytest tests/ -v

# 运行特定类型的测试
pytest tests/unit/ -v                    # 只运行单元测试
pytest tests/integration/ -v            # 只运行集成测试
pytest tests/performance/ -v            # 只运行性能测试

# 运行特定测试文件
pytest tests/unit/test_risk_analysis.py -v

# 运行特定测试类
pytest tests/unit/test_risk_analysis.py::TestRiskAnalysis -v

# 运行特定测试方法
pytest tests/unit/test_risk_analysis.py::TestRiskAnalysis::test_calculate_var -v
```

### 运行带标记的测试

```bash
# 运行单元测试
pytest -m unit -v

# 运行集成测试
pytest -m integration -v

# 运行性能测试
pytest -m performance -v

# 跳过慢速测试
pytest -m "not slow" -v
```

## 📊 测试覆盖率

### 生成覆盖率报告

```bash
# 生成HTML覆盖率报告
pytest tests/ --cov=core --cov=api --cov-report=html

# 生成终端覆盖率报告
pytest tests/ --cov=core --cov=api --cov-report=term-missing

# 生成XML覆盖率报告（用于CI）
pytest tests/ --cov=core --cov=api --cov-report=xml
```

生成的HTML报告在 `htmlcov/index.html`

### 覆盖率目标

- 风险分析模块：>90%
- 数据服务模块：>85%
- 交易引擎模块：>80%
- 策略引擎模块：>75%
- 整体覆盖率：>70%

## 🔎 v2.1.4 快速健康检查

当前版本在 `tests/test_v3_smoke.py` 中提供了一组**轻量级冒烟测试**，用于快速验证 v2.1.4 代码是否有基础问题：

```bash
# 仅运行 v3 冒烟测试
pytest tests/test_v3_smoke.py -q
```

检查内容包括：

- `core.version.VERSION` 是否为 `2.1.4`，且与 `api.main.app.version` 一致
- `/api/health` 是否可以正常返回，且返回结构中包含 `status`、`service`、`version` 和 `memory` 信息

如需做真实运行态发布验收，请先启动前后端服务，再执行：

```bash
RUN_EXTERNAL_E2E=1 pytest tests/e2e/test_release_validation.py -q
```

## 🧪 测试类型说明

### 单元测试

测试单个模块或函数的功能，使用mock隔离依赖。

**位置**: `tests/unit/`

**示例**:
- `test_risk_analysis.py` - 风险分析函数测试
- `test_data_service.py` - 数据服务测试
- `test_trading_engine.py` - 交易引擎测试

### 集成测试

测试多个模块协同工作的完整流程。

**位置**: `tests/integration/`

**示例**:
- `test_trading_flow.py` - 从信号生成到订单执行的完整流程
- `test_data_pipeline.py` - 数据获取、验证、修复、存储的完整流程

### 性能测试

测试系统在负载下的性能表现，确保满足性能要求。

**位置**: `tests/performance/`

**示例**:
- `test_data_loading.py` - 数据加载性能测试
- `test_backtest_performance.py` - 回测性能测试

## 📝 编写测试

### 基本测试结构

```python
import pytest
from core.module import function

class TestModule:
    """测试模块"""
    
    @pytest.fixture
    def sample_data(self):
        """创建测试数据"""
        return ...
    
    def test_function(self, sample_data):
        """测试函数"""
        result = function(sample_data)
        assert result is not None
```

### 使用共享Fixtures

`conftest.py` 中定义的fixtures可以在所有测试文件中使用：

```python
def test_example(sample_price_data, sample_account):
    """使用共享fixtures"""
    # sample_price_data 和 sample_account 自动注入
    pass
```

### Mock外部依赖

```python
from unittest.mock import patch

@patch('core.data_service._load_price_data_remote')
def test_with_mock(mock_load):
    mock_load.return_value = sample_data
    result = load_price_data(...)
    assert result is not None
```

## ⚙️ 测试配置

### pytest.ini

配置文件定义了：
- 测试发现模式
- 标记定义
- 输出选项
- 覆盖率配置

### 环境变量

可以通过环境变量配置测试：

```bash
# 设置测试数据库路径
export TEST_DB_PATH=/tmp/test.db

# 设置测试数据目录
export TEST_DATA_DIR=/tmp/test_data
```

## 🔍 调试测试

### 运行失败时进入调试器

```bash
pytest tests/ --pdb
```

### 打印详细输出

```bash
pytest tests/ -v -s
```

### 只运行失败的测试

```bash
pytest tests/ --lf
```

## 📈 CI/CD集成

### GitHub Actions示例

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-cov
      - run: pytest tests/ --cov=core --cov=api --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## 📋 测试清单

### 已实现测试

- ✅ 风险管理模块（风险类型、仓位管理、止损止盈、风险监控）
- ✅ 订单管理模块（订单创建、提交、成交）
- ✅ 滑点模型和执行算法
- ✅ 数据验证和修复
- ✅ 数据库和多级缓存
- ✅ RBAC和审计日志
- ✅ 系统监控和告警
- ✅ 风险分析（VaR、CVaR、最大回撤）
- ✅ 数据服务
- ✅ 交易引擎
- ✅ 策略引擎
- ✅ 集成测试（交易流程、数据管道）
- ✅ 性能测试（数据加载、回测）

### 待补充测试

- ⏳ 更多数据服务场景
- ⏳ 更多交易引擎场景
- ⏳ API路由测试
- ⏳ WebSocket测试

## ⚠️ 注意事项

1. **测试隔离**：每个测试应该独立，不依赖其他测试的状态
2. **Mock使用**：合理使用mock，避免过度mock导致测试不真实
3. **性能基准**：性能测试的阈值应该根据实际环境调整
4. **测试数据**：使用fixtures创建测试数据，避免硬编码
5. **清理资源**：测试后清理临时文件和资源

## 🔗 相关文档

- [pytest文档](https://docs.pytest.org/)
- [pytest-cov文档](https://pytest-cov.readthedocs.io/)
- [优化建议.md](../优化建议.md) - 完整的优化建议文档
