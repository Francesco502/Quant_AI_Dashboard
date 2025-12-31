"""
策略管理器模块（阶段三：策略与AI融合）

职责：
- 加载和管理策略配置
- 创建和缓存策略实例
- 支持策略版本管理
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from .strategy_framework import (
    BaseStrategy,
    TechnicalStrategy,
    AIStrategy,
    EnsembleStrategy,
    STRATEGIES_DIR,
    STRATEGIES_CONFIG_FILE,
    _ensure_strategies_dir,
)


class StrategyManager:
    """策略管理器"""

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化策略管理器

        参数:
            config_file: 配置文件路径（None则使用默认路径）
        """
        self.config_file = config_file or STRATEGIES_CONFIG_FILE
        self.strategies: Dict[str, BaseStrategy] = {}
        self.config: Dict = {}
        self._load_config()

    def _load_config(self) -> None:
        """加载策略配置"""
        _ensure_strategies_dir()
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"加载策略配置失败: {e}")
                self.config = {"strategies": []}
        else:
            # 创建默认配置
            self.config = {"strategies": []}
            self._save_config()

    def _save_config(self) -> None:
        """保存策略配置"""
        _ensure_strategies_dir()
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def _create_strategy_from_config(self, strategy_config: Dict) -> Optional[BaseStrategy]:
        """
        从配置创建策略实例

        参数:
            strategy_config: 策略配置字典

        返回:
            策略实例，失败返回None
        """
        strategy_id = strategy_config.get("strategy_id")
        strategy_type = strategy_config.get("type", "technical")
        version = strategy_config.get("version", "v1.0")
        params = strategy_config.get("params", {})

        try:
            if strategy_type == "technical":
                return TechnicalStrategy(
                    strategy_id=strategy_id,
                    version=version,
                    **params
                )
            elif strategy_type == "ai":
                return AIStrategy(
                    strategy_id=strategy_id,
                    version=version,
                    **params
                )
            elif strategy_type == "ensemble":
                return EnsembleStrategy(
                    strategy_id=strategy_id,
                    version=version,
                    **params
                )
            else:
                print(f"未知的策略类型: {strategy_type}")
                return None
        except Exception as e:
            print(f"创建策略失败 ({strategy_id}): {e}")
            return None

    def get_strategy(self, strategy_id: str) -> Optional[BaseStrategy]:
        """
        获取策略实例（带缓存）

        参数:
            strategy_id: 策略ID

        返回:
            策略实例，不存在返回None
        """
        # 先检查缓存
        if strategy_id in self.strategies:
            return self.strategies[strategy_id]

        # 从配置加载
        for strategy_config in self.config.get("strategies", []):
            if strategy_config.get("strategy_id") == strategy_id:
                strategy = self._create_strategy_from_config(strategy_config)
                if strategy:
                    self.strategies[strategy_id] = strategy
                    return strategy

        return None

    def list_strategies(self) -> List[Dict]:
        """
        列出所有策略配置

        返回:
            策略配置列表
        """
        return self.config.get("strategies", [])

    def add_strategy(self, strategy_config: Dict) -> bool:
        """
        添加策略配置

        参数:
            strategy_config: 策略配置字典

        返回:
            是否成功
        """
        strategy_id = strategy_config.get("strategy_id")
        if not strategy_id:
            return False

        # 检查是否已存在
        strategies = self.config.get("strategies", [])
        for i, s in enumerate(strategies):
            if s.get("strategy_id") == strategy_id:
                # 更新现有策略
                strategies[i] = strategy_config
                self._save_config()
                # 清除缓存
                if strategy_id in self.strategies:
                    del self.strategies[strategy_id]
                return True

        # 添加新策略
        strategies.append(strategy_config)
        self.config["strategies"] = strategies
        self._save_config()
        return True

    def remove_strategy(self, strategy_id: str) -> bool:
        """
        删除策略配置

        参数:
            strategy_id: 策略ID

        返回:
            是否成功
        """
        strategies = self.config.get("strategies", [])
        original_count = len(strategies)
        self.config["strategies"] = [
            s for s in strategies if s.get("strategy_id") != strategy_id
        ]
        
        if len(self.config["strategies"]) < original_count:
            self._save_config()
            # 清除缓存
            if strategy_id in self.strategies:
                del self.strategies[strategy_id]
            return True
        
        return False

    def reload_config(self) -> None:
        """重新加载配置"""
        self.strategies.clear()
        self._load_config()


# 全局单例
_strategy_manager_instance: Optional[StrategyManager] = None


def get_strategy_manager() -> StrategyManager:
    """获取策略管理器单例"""
    global _strategy_manager_instance
    if _strategy_manager_instance is None:
        _strategy_manager_instance = StrategyManager()
    return _strategy_manager_instance

