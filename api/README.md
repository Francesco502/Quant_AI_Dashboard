# Quant-AI Dashboard API 文档

## 快速开始

### 启动 API 服务

**Windows (批处理文件):**
```bash
start_api.bat
```

**Windows (PowerShell):**
```powershell
.\start_api.ps1
```

**手动启动:**
```bash
cd Quant_AI_Dashboard
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 访问 API 文档

启动后访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/api/health

## API 端点概览

### 1. 策略管理 (`/api/strategies`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/strategies/` | 获取所有策略列表 |
| GET | `/api/strategies/{strategy_id}` | 获取指定策略详情 |
| POST | `/api/strategies/` | 创建新策略 |
| DELETE | `/api/strategies/{strategy_id}` | 删除策略 |
| POST | `/api/strategies/{strategy_id}/generate-signals` | 使用策略生成信号 |

**示例：**
```bash
# 获取所有策略
curl http://localhost:8000/api/strategies/

# 使用策略生成信号
curl -X POST http://localhost:8000/api/strategies/hybrid_v1/generate-signals \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["159755.SZ", "002611"], "days": 365}'
```

### 2. 信号管理 (`/api/signals`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/signals/` | 获取信号列表（支持筛选） |
| GET | `/api/signals/latest` | 获取最新信号 |
| PUT | `/api/signals/{ticker}/status` | 更新信号状态 |
| GET | `/api/signals/stats` | 获取信号统计 |

**示例：**
```bash
# 获取最近7天的信号
curl "http://localhost:8000/api/signals/?days=7&status=pending"

# 获取信号统计
curl http://localhost:8000/api/signals/stats?days=7
```

### 3. 数据获取 (`/api/data`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/data/prices` | 获取价格数据（POST） |
| GET | `/api/data/prices` | 获取价格数据（GET） |
| POST | `/api/data/ohlcv` | 获取OHLCV数据 |

**示例：**
```bash
# GET方式获取价格数据
curl "http://localhost:8000/api/data/prices?tickers=159755.SZ,002611&days=365"

# POST方式获取价格数据
curl -X POST http://localhost:8000/api/data/prices \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["159755.SZ", "002611"], "days": 365, "data_sources": ["AkShare"]}'
```

### 4. AI预测 (`/api/forecasting`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/forecasting/predict` | 快速预测（使用生产模型） |
| GET | `/api/forecasting/predict/{ticker}` | 快速预测（GET方式） |
| POST | `/api/forecasting/batch-predict` | 批量预测 |

**示例：**
```bash
# 预测单个标的
curl "http://localhost:8000/api/forecasting/predict/159755.SZ?horizon=5&model_type=xgboost"

# 批量预测
curl -X POST http://localhost:8000/api/forecasting/batch-predict \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["159755.SZ", "002611"], "horizon": 5, "model_type": "xgboost"}'
```

### 5. 交易执行 (`/api/trading`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/trading/execute` | 执行信号 |
| GET | `/api/trading/risk-check` | 风控检查 |

**示例：**
```bash
# 执行信号
curl -X POST http://localhost:8000/api/trading/execute \
  -H "Content-Type: application/json" \
  -d '{
    "signals": [
      {"ticker": "159755.SZ", "signal": 0.5, "direction": 1, "confidence": 0.8, "action": "买入"}
    ],
    "strategy_id": "hybrid_v1",
    "total_capital": 1000000.0,
    "max_positions": 5,
    "tickers": ["159755.SZ"]
  }'
```

### 6. 模型管理 (`/api/models`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models/registry` | 获取模型注册表 |
| GET | `/api/models/production/{ticker}` | 获取生产模型 |
| GET | `/api/models/history/{ticker}` | 获取模型历史 |
| GET | `/api/models/available` | 获取可用模型列表 |

### 7. 账户管理 (`/api/accounts`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/accounts/paper` | 获取模拟账户信息 |
| GET | `/api/accounts/paper/equity` | 获取权益历史 |
| GET | `/api/accounts/paper/positions` | 获取当前持仓 |
| GET | `/api/accounts/paper/trades` | 获取交易记录 |

## WebSocket 接口

### 通用 WebSocket (`/ws`)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
  console.log('收到消息:', event.data);
};
```

### 信号实时推送 (`/ws/signals`)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/signals');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'signals_update') {
    console.log('信号更新:', data.data);
  }
};
```

## 响应格式

### 成功响应
```json
{
  "status": "success",
  "data": {...},
  "message": "操作成功"
}
```

### 错误响应
```json
{
  "detail": "错误描述"
}
```

## 认证（待实现）

当前版本未实现认证，生产环境建议添加：
- JWT Token 认证
- API Key 认证
- OAuth2

## 注意事项

1. **CORS配置**: 当前允许所有来源，生产环境应限制具体域名
2. **错误处理**: 所有API都有统一的错误处理
3. **数据格式**: 日期时间使用ISO格式字符串
4. **异步处理**: 所有路由都是异步的，支持高并发

## 与 Streamlit 共存

API 服务可以与 Streamlit Dashboard 同时运行：
- Streamlit: http://localhost:8501 (Dashboard)
- FastAPI: http://localhost:8000 (API)

两者共享相同的业务逻辑层（`core/` 模块），互不干扰。

