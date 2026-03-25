"""风险管理配置持久化模块

职责：
- 加载和保存风险管理配置
- 提供配置的默认值和验证
"""

from __future__ import annotations

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

from .risk_types import RiskLimits, PositionLimit
from .position_manager import SectorInfo


CONFIG_DIR = Path(__file__).parent.parent
RISK_CONFIG_FILE = CONFIG_DIR / "risk_config.json"


def get_default_risk_config() -> Dict[str, Any]:
    """获取默认风险配置"""
    return {
        "risk_limits": {
            "max_position_size": 0.1,
            "max_total_exposure": 0.95,
            "max_sector_exposure": 0.3,
            "max_single_stock": 0.05,
            "max_daily_loss": 0.05,
            "max_total_loss": 0.2,
            "stop_loss_threshold": 0.08,
            "max_correlation": 0.8,
            "min_liquidity_ratio": 0.1,
        },
        "position_limits": {},
        "sector_limits": {},
        "market_limits": {},
        "total_position_limit": 0.95,
        "sector_info": {},
        "alert_config": {
            "email": {
                "enabled": False,
                "smtp_server": "",
                "smtp_port": 587,
                "username": "",
                "password": "",
            },
            "sms": {
                "enabled": False,
                "provider": "twilio",
                "api_key": "",
                "api_secret": "",
                "from_number": "",
                "to_numbers": [],
                "api_base_url": "https://api.twilio.com",
            },
            "webhook": {
                "enabled": False,
                "url": "",
            },
            "log_file": "logs/risk_alerts.log",
        },
        "stop_loss_defaults": {
            "stop_percentage": 0.05,
            "take_profit_percentage": 0.1,
        },
    }


def load_risk_config() -> Dict[str, Any]:
    """加载风险配置"""
    if not RISK_CONFIG_FILE.exists():
        # 如果配置文件不存在，创建默认配置
        config = get_default_risk_config()
        save_risk_config(config)
        return config
    
    try:
        with open(RISK_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # 合并默认配置，确保所有字段都存在
        default_config = get_default_risk_config()
        for key, default_value in default_config.items():
            if key not in config:
                config[key] = default_value
            elif isinstance(default_value, dict):
                for sub_key, sub_default in default_value.items():
                    if sub_key not in config[key]:
                        config[key][sub_key] = sub_default
        
        return config
    except Exception as e:
        print(f"加载风险配置失败: {e}，使用默认配置")
        return get_default_risk_config()


def save_risk_config(config: Dict[str, Any]) -> bool:
    """保存风险配置"""
    try:
        # 确保目录存在
        RISK_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(RISK_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"保存风险配置失败: {e}")
        return False


def config_to_risk_limits(config: Dict[str, Any]) -> RiskLimits:
    """将配置转换为 RiskLimits 对象"""
    risk_limits_config = config.get("risk_limits", {})
    return RiskLimits(
        max_position_size=risk_limits_config.get("max_position_size", 0.1),
        max_total_exposure=risk_limits_config.get("max_total_exposure", 0.95),
        max_sector_exposure=risk_limits_config.get("max_sector_exposure", 0.3),
        max_single_stock=risk_limits_config.get("max_single_stock", 0.05),
        max_daily_loss=risk_limits_config.get("max_daily_loss", 0.05),
        max_total_loss=risk_limits_config.get("max_total_loss", 0.2),
        stop_loss_threshold=risk_limits_config.get("stop_loss_threshold", 0.08),
        max_correlation=risk_limits_config.get("max_correlation", 0.8),
        min_liquidity_ratio=risk_limits_config.get("min_liquidity_ratio", 0.1),
    )


def config_to_sector_info(config: Dict[str, Any]) -> Dict[str, SectorInfo]:
    """将配置转换为 SectorInfo 字典"""
    sector_info_config = config.get("sector_info", {})
    result = {}
    
    for symbol, info in sector_info_config.items():
        result[symbol] = SectorInfo(
            symbol=symbol,
            sector=info.get("sector", ""),
            market=info.get("market", "")
        )
    
    return result


def config_to_position_limits(config: Dict[str, Any]) -> Dict[str, PositionLimit]:
    """将配置转换为 PositionLimit 字典"""
    position_limits_config = config.get("position_limits", {})
    result = {}
    
    for symbol, limit_config in position_limits_config.items():
        result[symbol] = PositionLimit(
            symbol=symbol,
            max_position=limit_config.get("max_position", 0),
            max_weight=limit_config.get("max_weight", 0.1),
            max_value=limit_config.get("max_value"),
        )
    
    return result


def risk_limits_to_config(risk_limits: RiskLimits) -> Dict[str, Any]:
    """将 RiskLimits 对象转换为配置字典"""
    return {
        "max_position_size": risk_limits.max_position_size,
        "max_total_exposure": risk_limits.max_total_exposure,
        "max_sector_exposure": risk_limits.max_sector_exposure,
        "max_single_stock": risk_limits.max_single_stock,
        "max_daily_loss": risk_limits.max_daily_loss,
        "max_total_loss": risk_limits.max_total_loss,
        "stop_loss_threshold": risk_limits.stop_loss_threshold,
        "max_correlation": risk_limits.max_correlation,
        "min_liquidity_ratio": risk_limits.min_liquidity_ratio,
    }


def sector_info_to_config(sector_info: Dict[str, SectorInfo]) -> Dict[str, Any]:
    """将 SectorInfo 字典转换为配置字典"""
    result = {}
    for symbol, info in sector_info.items():
        result[symbol] = {
            "sector": info.sector,
            "market": info.market,
        }
    return result


def position_limits_to_config(position_limits: Dict[str, PositionLimit]) -> Dict[str, Any]:
    """将 PositionLimit 字典转换为配置字典"""
    result = {}
    for symbol, limit in position_limits.items():
        result[symbol] = {
            "max_position": limit.max_position,
            "max_weight": limit.max_weight,
            "max_value": limit.max_value,
        }
    return result
