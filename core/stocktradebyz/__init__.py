"""
StockTradebyZ 战法模块

本模块包含从原 StockTradebyZ 项目整合的选股战法实现：
- Selector.py: 核心选股逻辑（BBIKDJ、SuperB1、补票、填坑、上穿60放量等）
- configs.json: 战法默认配置

数据来源：
- 使用 Quant_AI_Dashboard 的统一数据服务（parquet 格式）
- 不再依赖原项目的 CSV 数据文件
"""

__all__ = []

