"""数据验证规则引擎

职责：
- 建立完善的数据验证规则
- 支持多种验证规则类型
- 可扩展的规则系统
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from .data_quality import QualityLevel


logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    rule_name: str
    message: str
    issue_type: str
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class ValidationRule(ABC):
    """验证规则基类"""
    
    def __init__(self, rule_name: str):
        self.rule_name = rule_name
        self.enabled = True
    
    @abstractmethod
    def check(self, data: pd.DataFrame | pd.Series, ticker: str) -> ValidationResult:
        """检查数据"""
        pass


class PriceRangeRule(ValidationRule):
    """价格范围规则"""
    
    def __init__(self, min: float = 0, max: float = 1000000):
        super().__init__("价格范围检查")
        self.min = min
        self.max = max
    
    def check(self, data: pd.DataFrame | pd.Series, ticker: str) -> ValidationResult:
        """检查价格是否在合理范围内"""
        if isinstance(data, pd.DataFrame):
            if "close" in data.columns:
                prices = data["close"]
            else:
                return ValidationResult(True, self.rule_name, "无价格列", "missing_column")
        else:
            prices = data
        
        invalid_prices = ((prices < self.min) | (prices > self.max)).sum()
        
        if invalid_prices > 0:
            return ValidationResult(
                False,
                self.rule_name,
                f"存在 {invalid_prices} 个价格超出范围 [{self.min}, {self.max}]",
                "price_range",
                {"invalid_count": invalid_prices, "min": self.min, "max": self.max}
            )
        
        return ValidationResult(True, self.rule_name, "价格范围正常", "price_range")


class PriceChangeRule(ValidationRule):
    """价格变化规则（单日涨跌幅限制）"""
    
    def __init__(self, max_change: float = 0.5):
        super().__init__("价格变化检查")
        self.max_change = max_change  # 最大涨跌幅（如0.5表示50%）
    
    def check(self, data: pd.DataFrame | pd.Series, ticker: str) -> ValidationResult:
        """检查单日涨跌幅是否超过限制"""
        if isinstance(data, pd.DataFrame):
            if "close" in data.columns:
                prices = data["close"]
            else:
                return ValidationResult(True, self.rule_name, "无价格列", "missing_column")
        else:
            prices = data
        
        if len(prices) < 2:
            return ValidationResult(True, self.rule_name, "数据点不足，跳过检查", "insufficient_data")
        
        returns = prices.pct_change().dropna()
        extreme_changes = (returns.abs() > self.max_change).sum()
        
        if extreme_changes > 0:
            return ValidationResult(
                False,
                self.rule_name,
                f"存在 {extreme_changes} 个交易日涨跌幅超过 {self.max_change*100:.0f}%",
                "price_change",
                {"extreme_count": extreme_changes, "max_change": self.max_change}
            )
        
        return ValidationResult(True, self.rule_name, "价格变化正常", "price_change")


class PriceContinuityRule(ValidationRule):
    """价格连续性规则"""
    
    def __init__(self, max_gap_days: int = 5):
        super().__init__("价格连续性检查")
        self.max_gap_days = max_gap_days
    
    def check(self, data: pd.DataFrame | pd.Series, ticker: str) -> ValidationResult:
        """检查价格数据的时间连续性"""
        if isinstance(data, pd.DataFrame):
            if not isinstance(data.index, pd.DatetimeIndex):
                return ValidationResult(True, self.rule_name, "非时间序列，跳过检查", "not_time_series")
            date_index = data.index
        else:
            if not isinstance(data.index, pd.DatetimeIndex):
                return ValidationResult(True, self.rule_name, "非时间序列，跳过检查", "not_time_series")
            date_index = data.index
        
        if len(date_index) < 2:
            return ValidationResult(True, self.rule_name, "数据点不足，跳过检查", "insufficient_data")
        
        date_diffs = date_index.to_series().diff().dt.days
        large_gaps = (date_diffs > self.max_gap_days).sum()
        
        if large_gaps > len(date_index) * 0.1:  # 超过10%的日期有较大间隔
            return ValidationResult(
                False,
                self.rule_name,
                f"数据连续性较差: {large_gaps} 个日期间隔超过 {self.max_gap_days} 天",
                "continuity",
                {"large_gaps": large_gaps, "max_gap_days": self.max_gap_days}
            )
        
        return ValidationResult(True, self.rule_name, "数据连续性正常", "continuity")


class VolumeRangeRule(ValidationRule):
    """成交量范围规则"""
    
    def __init__(self, min: float = 0):
        super().__init__("成交量范围检查")
        self.min = min
    
    def check(self, data: pd.DataFrame | pd.Series, ticker: str) -> ValidationResult:
        """检查成交量是否在合理范围内"""
        if isinstance(data, pd.DataFrame):
            if "volume" not in data.columns:
                return ValidationResult(True, self.rule_name, "无成交量列", "missing_column")
            volumes = data["volume"]
        else:
            return ValidationResult(True, self.rule_name, "单列数据无成交量", "not_ohlcv")
        
        invalid_volumes = (volumes < self.min).sum()
        
        if invalid_volumes > 0:
            return ValidationResult(
                False,
                self.rule_name,
                f"存在 {invalid_volumes} 个成交量小于 {self.min}",
                "volume_range",
                {"invalid_count": invalid_volumes, "min": self.min}
            )
        
        return ValidationResult(True, self.rule_name, "成交量范围正常", "volume_range")


class VolumeSpikeRule(ValidationRule):
    """成交量异常检测规则"""
    
    def __init__(self, threshold: float = 10.0):
        super().__init__("成交量异常检测")
        self.threshold = threshold  # 异常倍数（如10表示10倍平均成交量）
    
    def check(self, data: pd.DataFrame | pd.Series, ticker: str) -> ValidationResult:
        """检测异常成交量"""
        if isinstance(data, pd.DataFrame):
            if "volume" not in data.columns:
                return ValidationResult(True, self.rule_name, "无成交量列", "missing_column")
            volumes = data["volume"]
        else:
            return ValidationResult(True, self.rule_name, "单列数据无成交量", "not_ohlcv")
        
        if len(volumes) < 10:
            return ValidationResult(True, self.rule_name, "数据点不足，跳过检查", "insufficient_data")
        
        avg_volume = volumes.mean()
        if avg_volume <= 0:
            return ValidationResult(True, self.rule_name, "平均成交量为0，跳过检查", "zero_volume")
        
        spikes = (volumes > avg_volume * self.threshold).sum()
        
        if spikes > 0:
            return ValidationResult(
                False,
                self.rule_name,
                f"存在 {spikes} 个异常成交量（超过平均值的 {self.threshold} 倍）",
                "volume_spike",
                {"spike_count": spikes, "threshold": self.threshold}
            )
        
        return ValidationResult(True, self.rule_name, "成交量正常", "volume_spike")


class OHLCConsistencyRule(ValidationRule):
    """OHLC一致性规则"""
    
    def __init__(self):
        super().__init__("OHLC一致性检查")
    
    def check(self, data: pd.DataFrame | pd.Series, ticker: str) -> ValidationResult:
        """检查OHLC数据的一致性"""
        if isinstance(data, pd.Series):
            return ValidationResult(True, self.rule_name, "单列数据无OHLC", "not_ohlcv")
        
        required_cols = ["open", "high", "low", "close"]
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            return ValidationResult(
                False,
                self.rule_name,
                f"缺少必需列: {', '.join(missing_cols)}",
                "missing_columns",
                {"missing_columns": missing_cols}
            )
        
        # 检查OHLC逻辑关系
        invalid_ohlc = (
            (data["high"] < data["low"]) |
            (data["high"] < data["open"]) |
            (data["high"] < data["close"]) |
            (data["low"] > data["open"]) |
            (data["low"] > data["close"])
        ).sum()
        
        if invalid_ohlc > 0:
            return ValidationResult(
                False,
                self.rule_name,
                f"OHLC逻辑错误: {invalid_ohlc} 条记录",
                "ohlc_consistency",
                {"invalid_count": invalid_ohlc}
            )
        
        return ValidationResult(True, self.rule_name, "OHLC一致性正常", "ohlc_consistency")


class MissingDataRule(ValidationRule):
    """缺失数据规则"""
    
    def __init__(self, max_missing_days: int = 5, max_missing_pct: float = 0.1):
        super().__init__("缺失数据检查")
        self.max_missing_days = max_missing_days
        self.max_missing_pct = max_missing_pct
    
    def check(self, data: pd.DataFrame | pd.Series, ticker: str) -> ValidationResult:
        """检查缺失数据"""
        if isinstance(data, pd.DataFrame):
            # 检查主要列（close或第一列）
            if "close" in data.columns:
                series = data["close"]
            else:
                series = data.iloc[:, 0]
        else:
            series = data
        
        if series.empty:
            return ValidationResult(
                False,
                self.rule_name,
                "数据为空",
                "missing_data",
                {"missing_count": len(series)}
            )
        
        missing_count = series.isna().sum()
        missing_pct = missing_count / len(series)
        
        if missing_count > self.max_missing_days or missing_pct > self.max_missing_pct:
            return ValidationResult(
                False,
                self.rule_name,
                f"缺失数据过多: {missing_count} 个 ({missing_pct*100:.1f}%)",
                "missing_data",
                {"missing_count": missing_count, "missing_pct": missing_pct}
            )
        
        return ValidationResult(True, self.rule_name, "缺失数据在可接受范围内", "missing_data")


class DataValidator:
    """数据验证器"""
    
    def __init__(self):
        """初始化数据验证器"""
        self.validation_rules: Dict[str, List[ValidationRule]] = {
            "price": [
                PriceRangeRule(min=0, max=1000000),
                PriceChangeRule(max_change=0.5),
                PriceContinuityRule(max_gap_days=5),
            ],
            "volume": [
                VolumeRangeRule(min=0),
                VolumeSpikeRule(threshold=10.0),
            ],
            "ohlc": [
                OHLCConsistencyRule(),
            ],
            "missing": [
                MissingDataRule(max_missing_days=5, max_missing_pct=0.1),
            ],
        }
        logger.info("数据验证器初始化完成")
    
    def add_rule(self, rule_type: str, rule: ValidationRule):
        """添加验证规则"""
        if rule_type not in self.validation_rules:
            self.validation_rules[rule_type] = []
        self.validation_rules[rule_type].append(rule)
        logger.debug(f"添加验证规则: {rule_type} - {rule.rule_name}")
    
    def remove_rule(self, rule_type: str, rule_name: str) -> bool:
        """移除验证规则"""
        if rule_type not in self.validation_rules:
            return False
        
        for i, rule in enumerate(self.validation_rules[rule_type]):
            if rule.rule_name == rule_name:
                del self.validation_rules[rule_type][i]
                logger.debug(f"移除验证规则: {rule_type} - {rule_name}")
                return True
        
        return False
    
    def validate(
        self,
        data: pd.DataFrame | pd.Series,
        ticker: str,
        rule_types: Optional[List[str]] = None
    ) -> List[ValidationResult]:
        """
        验证数据

        Args:
            data: 数据（DataFrame或Series）
            ticker: 标的代码
            rule_types: 要执行的规则类型列表（可选，默认执行所有）

        Returns:
            验证结果列表
        """
        results: List[ValidationResult] = []
        
        rule_types = rule_types or list(self.validation_rules.keys())
        
        for rule_type in rule_types:
            if rule_type not in self.validation_rules:
                continue
            
            for rule in self.validation_rules[rule_type]:
                if not rule.enabled:
                    continue
                
                try:
                    result = rule.check(data, ticker)
                    results.append(result)
                except Exception as e:
                    logger.error(f"验证规则执行失败: {rule.rule_name} - {e}")
                    results.append(ValidationResult(
                        False,
                        rule.rule_name,
                        f"规则执行失败: {e}",
                        "rule_error"
                    ))
        
        return results
    
    def validate_summary(
        self,
        data: pd.DataFrame | pd.Series,
        ticker: str,
        rule_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        验证数据并返回摘要

        Args:
            data: 数据
            ticker: 标的代码
            rule_types: 要执行的规则类型列表（可选）

        Returns:
            验证摘要字典
        """
        results = self.validate(data, ticker, rule_types)
        
        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count
        
        issues = [r for r in results if not r.passed]
        
        # 确定质量等级
        if failed_count == 0:
            level = QualityLevel.EXCELLENT
        elif failed_count <= 2:
            level = QualityLevel.GOOD
        elif failed_count <= 4:
            level = QualityLevel.WARNING
        else:
            level = QualityLevel.ERROR
        
        return {
            "ticker": ticker,
            "level": level,
            "passed": passed_count,
            "failed": failed_count,
            "total": len(results),
            "issues": [
                {
                    "rule": issue.rule_name,
                    "message": issue.message,
                    "type": issue.issue_type,
                    "details": issue.details,
                }
                for issue in issues
            ],
            "all_results": [
                {
                    "rule": r.rule_name,
                    "passed": r.passed,
                    "message": r.message,
                    "type": r.issue_type,
                }
                for r in results
            ],
        }

