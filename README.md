# Quant-AI-Dashboard

> 生产级量化交易系统 - 集成数据管理、AI预测、风险管理、交易执行等功能的一体化平台

[![Version](https://img.shields.io/badge/version-v0.2.0-blue.svg)](https://github.com/Francesco502/Quant_AI_Dashboard/releases)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 目录

- [项目简介](#项目简介)
- [核心功能](#核心功能)
- [快速开始](#快速开始)
- [系统架构](#系统架构)
- [文档导航](#文档导航)
- [技术栈](#技术栈)
- [开发指南](#开发指南)
- [部署指南](#部署指南)

## 🎯 项目简介

Quant-AI-Dashboard 是一个功能完整的量化交易系统，集成了数据获取、AI预测、策略回测、风险管理、交易执行等核心功能。系统采用模块化设计，支持多数据源、多模型、多策略，适用于量化研究、策略开发和模拟交易。

### 主要特性

- ✅ **多数据源支持**：AkShare、Tushare、yfinance等
- ✅ **AI预测模型**：XGBoost、LightGBM、LSTM、GRU、Prophet等
- ✅ **完整风险管理**：实时监控、仓位管理、止损止盈
- ✅ **交易执行系统**：订单管理、滑点模型、执行算法（TWAP/VWAP）
- ✅ **系统监控告警**：健康检查、指标收集、多通道告警
- ✅ **Web界面**：Streamlit Dashboard + FastAPI RESTful API
- ✅ **Docker部署**：一键部署，7×24小时运行

## 🚀 核心功能

### 1. 数据管理
- 多数据源自动切换和fallback
- 本地数据仓库（Parquet格式）
- 数据质量验证和自动修复
- 数据版本管理

### 2. AI预测
- 支持多种机器学习模型
- 离线训练和在线部署
- 模型注册和版本管理
- 批量预测和实时预测

### 3. 策略系统
- 技术指标策略
- AI驱动策略
- 混合策略（Ensemble）
- 策略回测和评估

### 4. 风险管理
- 实时风险监控
- 多层级仓位限制
- 止损止盈管理
- 风险事件告警

### 5. 交易执行
- 完整订单生命周期管理
- 多种执行算法（TWAP/VWAP）
- 滑点模型
- 模拟交易和实盘对接

### 6. 系统监控
- 系统指标收集（CPU、内存、磁盘）
- 业务指标追踪
- 健康检查
- 多通道告警（邮件、Webhook、Telegram等）

## 🏃 快速开始

### 环境要求

- Python 3.10+
- 至少 2GB 可用磁盘空间
- 网络连接（用于数据获取）

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd Quant_AI_Dashboard
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
cp env.example .env
# 编辑 .env 文件，设置必要的配置
```

4. **启动Dashboard**
```bash
# Windows
start_dashboard.bat

# Linux/macOS
./start_dashboard.sh

# 或直接使用streamlit
streamlit run app.py
```

5. **访问系统**
- Dashboard: http://localhost:8501
- API文档: http://localhost:8000/docs

### Docker部署（推荐）

```bash
# 使用docker-compose一键部署
docker compose up -d

# 查看日志
docker compose logs -f dashboard
docker compose logs -f daemon
```

详细部署说明请参考 [部署指南](docs/运维手册.md#docker部署)

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Web界面层                              │
│  ┌──────────────┐              ┌──────────────┐        │
│  │ Streamlit    │              │ FastAPI      │        │
│  │ Dashboard    │              │ RESTful API  │        │
│  └──────────────┘              └──────────────┘        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    业务逻辑层                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│
│  │ 数据服务 │  │ AI预测   │  │ 策略引擎 │  │ 交易引擎 ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘│
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│
│  │ 风险管理 │  │ 订单管理 │  │ 系统监控 │  │ 后台服务 ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘│
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    数据存储层                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│
│  │ 价格数据 │  │ 模型文件 │  │ 账户数据 │  │ 信号数据 ││
│  │ (Parquet)│  │  (.pkl)  │  │  (JSON)  │  │  (CSV)   ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘│
└─────────────────────────────────────────────────────────┘
```

详细架构说明请参考 [架构设计文档](docs/架构设计.md)

## 📚 文档导航

### 核心文档
- [架构设计文档](docs/架构设计.md) - 系统架构、数据流、模块关系
- [开发指南](docs/开发指南.md) - 环境搭建、代码规范、开发流程
- [运维手册](docs/运维手册.md) - 部署、监控、故障排查

### 功能文档
- [模型训练与部署](docs/模型训练与部署.md) - 离线训练、在线部署流程
- [核心模块使用说明](docs/核心模块使用说明.md) - 风险管理、交易执行、监控系统
- [API文档](api/README.md) - RESTful API接口说明
- [测试指南](tests/README.md) - 测试体系和使用说明

### 部署文档
- [Docker部署指南](DOCKER_DEPLOY.md) - Docker容器化部署详细说明
- [镜像构建与推送](docs/镜像构建与推送.md) - 如何构建和推送Docker镜像
- [版本更新指南](docs/版本更新指南.md) - 版本更新步骤和注意事项
- [部署前检查清单](部署前检查清单.md) - 部署前必须检查项

### 配置文档
- [数据目录结构](DATA_LAYOUT.md) - 数据存储结构说明
- [数据源对比](数据源对比文档.md) - 各数据源对比和选择建议

### 优化文档
- [优化建议](优化建议.md) - 生产级优化建议和实施路线图

## 🛠️ 技术栈

### 前端
- **Streamlit** - Web界面框架
- **Plotly** - 交互式图表
- **Pandas** - 数据处理

### 后端
- **FastAPI** - RESTful API框架
- **Python 3.10+** - 主要编程语言

### 数据科学
- **XGBoost/LightGBM** - 梯度提升模型
- **PyTorch** - 深度学习框架（LSTM/GRU）
- **Prophet** - 时间序列预测
- **scikit-learn** - 机器学习工具

### 数据源
- **AkShare** - 中国A股数据
- **Tushare** - 专业金融数据
- **yfinance** - 全球市场数据

### 基础设施
- **Docker** - 容器化部署
- **SQLite** - 轻量级数据库
- **Parquet** - 列式存储格式

## 👨‍💻 开发指南

### 代码结构

```
Quant_AI_Dashboard/
├── app.py                 # Streamlit主应用
├── api/                   # FastAPI接口
│   ├── main.py           # API入口
│   └── routers/          # 路由模块
├── core/                  # 核心业务逻辑
│   ├── data_service.py   # 数据服务
│   ├── forecasting.py    # 预测模块
│   ├── risk_analysis.py  # 风险分析
│   ├── trading_engine.py # 交易引擎
│   └── monitoring/       # 监控模块
├── data/                  # 数据存储
│   ├── prices/          # 价格数据
│   ├── models/          # 模型文件
│   └── signals/         # 信号数据
├── tests/                # 测试代码
└── docs/                 # 文档目录
```

详细开发指南请参考 [开发指南](docs/开发指南.md)

## 🚢 部署指南

### 本地部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp env.example .env
# 编辑 .env 文件

# 3. 启动服务
streamlit run app.py
python -m uvicorn api.main:app --reload
```

### Docker部署

```bash
# 使用docker-compose
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f
```

详细部署说明请参考 [运维手册](docs/运维手册.md)

## 📊 测试

```bash
# 运行所有测试
pytest tests/ -v

# 生成覆盖率报告
pytest tests/ --cov=core --cov=api --cov-report=html

# 运行特定类型测试
pytest tests/unit/ -v          # 单元测试
pytest tests/integration/ -v   # 集成测试
pytest tests/performance/ -v   # 性能测试
```

详细测试说明请参考 [测试指南](tests/README.md)

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📝 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🔗 相关资源

- [Streamlit文档](https://docs.streamlit.io/)
- [FastAPI文档](https://fastapi.tiangolo.com/)
- [XGBoost文档](https://xgboost.readthedocs.io/)
- [AkShare文档](https://akshare.readthedocs.io/)

## 📧 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 Issue
- 发送邮件

---

**当前版本**: v0.2.0（由 Initial commit: Dashboard v0.1.4 更新）  
**最后更新**: 2026-02-06

