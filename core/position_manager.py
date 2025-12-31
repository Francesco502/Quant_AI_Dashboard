"""仓位管理系统

职责：
- 管理多层级仓位限制（单标的、行业、市场、总仓位）
- 检查仓位是否超过限制
- 计算可用仓位额度
"""

from __future__ import annotations

from typing import Dict, Optional, List
from dataclasses import dataclass
import logging

from .risk_types import PositionLimit
from .account import compute_equity


logger = logging.getLogger(__name__)


@dataclass
class SectorInfo:
    """行业信息"""
    symbol: str
    sector: str
    market: str  # 'A股', '美股', '港股', '加密货币' 等


class PositionManager:
    """仓位管理器"""

    def __init__(self, sector_info: Optional[Dict[str, SectorInfo]] = None):
        """
        初始化仓位管理器

        Args:
            sector_info: 标的的行业和市场信息字典 {symbol: SectorInfo}
        """
        # 仓位限制配置
        self.position_limits: Dict[str, PositionLimit] = {}
        
        # 行业和市场分类信息
        self.sector_info: Dict[str, SectorInfo] = sector_info or {}
        
        # 行业限制（行业代码 -> 最大权重）
        self.sector_limits: Dict[str, float] = {}
        
        # 市场限制（市场代码 -> 最大权重）
        self.market_limits: Dict[str, float] = {}
        
        # 总仓位限制
        self.total_position_limit: float = 0.95  # 默认95%
        
        logger.info("仓位管理器初始化完成")

    def add_position_limit(self, limit: PositionLimit):
        """添加单标的仓位限制"""
        self.position_limits[limit.symbol] = limit
        logger.debug(f"添加仓位限制: {limit.symbol}, 最大权重={limit.max_weight}")

    def set_sector_limit(self, sector: str, max_weight: float):
        """设置行业仓位限制"""
        self.sector_limits[sector] = max_weight
        logger.debug(f"设置行业限制: {sector}, 最大权重={max_weight}")

    def set_market_limit(self, market: str, max_weight: float):
        """设置市场仓位限制"""
        self.market_limits[market] = max_weight
        logger.debug(f"设置市场限制: {market}, 最大权重={max_weight}")

    def set_total_position_limit(self, max_weight: float):
        """设置总仓位限制"""
        self.total_position_limit = max_weight
        logger.debug(f"设置总仓位限制: {max_weight}")

    def check_position_limit(
        self,
        symbol: str,
        quantity: int,
        portfolio: Dict,
        current_prices: Dict[str, float]
    ) -> tuple[bool, str]:
        """
        检查是否超过仓位限制

        Args:
            symbol: 标的代码
            quantity: 目标持仓数量（正数为买入，负数为卖出）
            portfolio: 账户字典
            current_prices: 当前价格字典

        Returns:
            (是否通过, 错误消息)
        """
        # 计算当前组合总价值
        total_equity = compute_equity(portfolio, current_prices)
        if total_equity <= 0:
            return False, "组合总价值无效"

        # 1. 检查单标的限制
        if symbol in self.position_limits:
            limit = self.position_limits[symbol]
            current_position = portfolio.get("positions", {}).get(symbol, 0)
            new_position = current_position + quantity
            
            # 检查数量限制
            if limit.max_position > 0 and abs(new_position) > limit.max_position:
                return False, f"{symbol} 持仓数量超过限制: {abs(new_position)} > {limit.max_position}"
            
            # 检查权重限制
            if limit.max_weight > 0:
                position_value = abs(new_position) * current_prices.get(symbol, 0)
                position_weight = position_value / total_equity if total_equity > 0 else 0
                if position_weight > limit.max_weight:
                    return False, f"{symbol} 持仓权重超过限制: {position_weight:.2%} > {limit.max_weight:.2%}"

        # 2. 检查行业集中度
        if symbol in self.sector_info:
            sector = self.sector_info[symbol].sector
            if sector in self.sector_limits:
                sector_weight = self._calculate_sector_weight(
                    sector, portfolio, current_prices, total_equity
                )
                max_sector_weight = self.sector_limits[sector]
                
                # 计算新增仓位后的行业权重
                symbol_price = current_prices.get(symbol, 0)
                if symbol_price > 0:
                    new_position = portfolio.get("positions", {}).get(symbol, 0) + quantity
                    new_sector_weight = sector_weight + (new_position * symbol_price) / total_equity
                    if new_sector_weight > max_sector_weight:
                        return False, f"行业 {sector} 集中度超过限制: {new_sector_weight:.2%} > {max_sector_weight:.2%}"

        # 3. 检查市场集中度
        if symbol in self.sector_info:
            market = self.sector_info[symbol].market
            if market in self.market_limits:
                market_weight = self._calculate_market_weight(
                    market, portfolio, current_prices, total_equity
                )
                max_market_weight = self.market_limits[market]
                
                # 计算新增仓位后的市场权重
                symbol_price = current_prices.get(symbol, 0)
                if symbol_price > 0:
                    new_position = portfolio.get("positions", {}).get(symbol, 0) + quantity
                    new_market_weight = market_weight + (new_position * symbol_price) / total_equity
                    if new_market_weight > max_market_weight:
                        return False, f"市场 {market} 集中度超过限制: {new_market_weight:.2%} > {max_market_weight:.2%}"

        # 4. 检查总仓位限制
        total_position_weight = self._calculate_total_position_weight(
            portfolio, current_prices, total_equity
        )
        symbol_price = current_prices.get(symbol, 0)
        if symbol_price > 0:
            new_position = portfolio.get("positions", {}).get(symbol, 0) + quantity
            new_total_weight = total_position_weight + (new_position * symbol_price) / total_equity
            if new_total_weight > self.total_position_limit:
                return False, f"总仓位超过限制: {new_total_weight:.2%} > {self.total_position_limit:.2%}"

        return True, ""

    def get_available_position(
        self,
        symbol: str,
        portfolio: Dict,
        current_prices: Dict[str, float]
    ) -> float:
        """
        获取可用仓位额度（以市值计算）

        Args:
            symbol: 标的代码
            portfolio: 账户字典
            current_prices: 当前价格字典

        Returns:
            可用仓位额度（市值）
        """
        total_equity = compute_equity(portfolio, current_prices)
        if total_equity <= 0:
            return 0.0

        price = current_prices.get(symbol, 0)
        if price <= 0:
            return 0.0

        # 获取单标的限制
        max_value = total_equity * 0.1  # 默认10%
        if symbol in self.position_limits:
            limit = self.position_limits[symbol]
            if limit.max_weight > 0:
                max_value = min(max_value, total_equity * limit.max_weight)
            if limit.max_value and limit.max_value > 0:
                max_value = min(max_value, limit.max_value)

        # 获取当前持仓市值
        current_position = portfolio.get("positions", {}).get(symbol, 0)
        current_value = abs(current_position) * price

        # 计算可用额度
        available_value = max(0, max_value - current_value)
        return available_value

    def _calculate_sector_weight(
        self,
        sector: str,
        portfolio: Dict,
        current_prices: Dict[str, float],
        total_equity: float
    ) -> float:
        """计算行业权重"""
        sector_value = 0.0
        positions = portfolio.get("positions", {}) or {}
        
        for symbol, quantity in positions.items():
            if quantity == 0:
                continue
            if symbol in self.sector_info and self.sector_info[symbol].sector == sector:
                price = current_prices.get(symbol, 0)
                sector_value += abs(quantity) * price
        
        return sector_value / total_equity if total_equity > 0 else 0.0

    def _calculate_market_weight(
        self,
        market: str,
        portfolio: Dict,
        current_prices: Dict[str, float],
        total_equity: float
    ) -> float:
        """计算市场权重"""
        market_value = 0.0
        positions = portfolio.get("positions", {}) or {}
        
        for symbol, quantity in positions.items():
            if quantity == 0:
                continue
            if symbol in self.sector_info and self.sector_info[symbol].market == market:
                price = current_prices.get(symbol, 0)
                market_value += abs(quantity) * price
        
        return market_value / total_equity if total_equity > 0 else 0.0

    def _calculate_total_position_weight(
        self,
        portfolio: Dict,
        current_prices: Dict[str, float],
        total_equity: float
    ) -> float:
        """计算总仓位权重"""
        total_position_value = 0.0
        positions = portfolio.get("positions", {}) or {}
        
        for symbol, quantity in positions.items():
            if quantity == 0:
                continue
            price = current_prices.get(symbol, 0)
            total_position_value += abs(quantity) * price
        
        return total_position_value / total_equity if total_equity > 0 else 0.0

    def get_position_summary(
        self,
        portfolio: Dict,
        current_prices: Dict[str, float]
    ) -> Dict:
        """获取仓位汇总信息"""
        total_equity = compute_equity(portfolio, current_prices)
        positions = portfolio.get("positions", {}) or {}
        
        summary = {
            "total_equity": total_equity,
            "total_position_value": 0.0,
            "total_position_weight": 0.0,
            "symbol_weights": {},
            "sector_weights": {},
            "market_weights": {},
        }
        
        # 计算各标的权重
        for symbol, quantity in positions.items():
            if quantity == 0:
                continue
            price = current_prices.get(symbol, 0)
            value = abs(quantity) * price
            weight = value / total_equity if total_equity > 0 else 0
            summary["symbol_weights"][symbol] = weight
            summary["total_position_value"] += value
            
            # 按行业汇总
            if symbol in self.sector_info:
                sector = self.sector_info[symbol].sector
                if sector not in summary["sector_weights"]:
                    summary["sector_weights"][sector] = 0.0
                summary["sector_weights"][sector] += weight
                
                # 按市场汇总
                market = self.sector_info[symbol].market
                if market not in summary["market_weights"]:
                    summary["market_weights"][market] = 0.0
                summary["market_weights"][market] += weight
        
        summary["total_position_weight"] = summary["total_position_value"] / total_equity if total_equity > 0 else 0.0
        
        return summary

