"""数据异常自动修复

职责：
- 自动检测并修复常见数据异常
- 支持多种修复策略
- 记录修复历史
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

from .data_validation import ValidationResult


logger = logging.getLogger(__name__)


@dataclass
class RepairResult:
    """修复结果"""
    success: bool
    repair_type: str
    message: str
    repaired_count: int = 0
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class RepairStrategy(ABC):
    """修复策略基类"""
    
    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        self.enabled = True
    
    @abstractmethod
    def repair(self, data: pd.DataFrame | pd.Series, issue: ValidationResult) -> tuple[pd.DataFrame | pd.Series, RepairResult]:
        """修复数据问题"""
        pass


class MissingDataRepair(RepairStrategy):
    """缺失数据修复策略"""
    
    def __init__(self, method: str = "forward_fill"):
        """
        初始化缺失数据修复

        Args:
            method: 修复方法 ('forward_fill', 'backward_fill', 'interpolate', 'drop')
        """
        super().__init__("缺失数据修复")
        self.method = method
    
    def repair(
        self,
        data: pd.DataFrame | pd.Series,
        issue: ValidationResult
    ) -> tuple[pd.DataFrame | pd.Series, RepairResult]:
        """修复缺失数据"""
        if isinstance(data, pd.DataFrame):
            repaired_data = data.copy()
            repaired_count = 0
            
            for col in repaired_data.columns:
                missing_before = repaired_data[col].isna().sum()
                
                if self.method == "forward_fill":
                    repaired_data[col] = repaired_data[col].ffill()
                elif self.method == "backward_fill":
                    repaired_data[col] = repaired_data[col].bfill()
                elif self.method == "interpolate":
                    repaired_data[col] = repaired_data[col].interpolate(method="linear")
                elif self.method == "drop":
                    repaired_data = repaired_data.dropna(subset=[col])
                
                missing_after = repaired_data[col].isna().sum()
                repaired_count += missing_before - missing_after
        else:
            repaired_data = data.copy()
            missing_before = repaired_data.isna().sum()
            
            if self.method == "forward_fill":
                repaired_data = repaired_data.ffill()
            elif self.method == "backward_fill":
                repaired_data = repaired_data.bfill()
            elif self.method == "interpolate":
                repaired_data = repaired_data.interpolate(method="linear")
            elif self.method == "drop":
                repaired_data = repaired_data.dropna()
            
            missing_after = repaired_data.isna().sum()
            repaired_count = missing_before - missing_after
        
        return repaired_data, RepairResult(
            success=True,
            repair_type="missing_data",
            message=f"使用 {self.method} 方法修复了 {repaired_count} 个缺失值",
            repaired_count=repaired_count,
            details={"method": self.method}
        )


class OutlierRepair(RepairStrategy):
    """异常值修复策略"""
    
    def __init__(self, method: str = "clip", z_score_threshold: float = 3.0):
        """
        初始化异常值修复

        Args:
            method: 修复方法 ('clip', 'remove', 'median', 'mean')
            z_score_threshold: Z分数阈值（用于检测异常值）
        """
        super().__init__("异常值修复")
        self.method = method
        self.z_score_threshold = z_score_threshold
    
    def repair(
        self,
        data: pd.DataFrame | pd.Series,
        issue: ValidationResult
    ) -> tuple[pd.DataFrame | pd.Series, RepairResult]:
        """修复异常值"""
        if isinstance(data, pd.DataFrame):
            repaired_data = data.copy()
            repaired_count = 0
            
            # 修复价格列
            price_cols = ["close", "open", "high", "low"]
            for col in price_cols:
                if col not in repaired_data.columns:
                    continue
                
                series = repaired_data[col]
                outliers = self._detect_outliers(series)
                outlier_count = outliers.sum()
                
                if outlier_count > 0:
                    if self.method == "clip":
                        # 使用分位数裁剪
                        q1 = series.quantile(0.25)
                        q3 = series.quantile(0.75)
                        iqr = q3 - q1
                        lower = q1 - 1.5 * iqr
                        upper = q3 + 1.5 * iqr
                        repaired_data[col] = series.clip(lower=lower, upper=upper)
                    elif self.method == "remove":
                        repaired_data = repaired_data[~outliers]
                    elif self.method == "median":
                        median_value = series.median()
                        repaired_data.loc[outliers, col] = median_value
                    elif self.method == "mean":
                        mean_value = series.mean()
                        repaired_data.loc[outliers, col] = mean_value
                    
                    repaired_count += outlier_count
        else:
            repaired_data = data.copy()
            outliers = self._detect_outliers(repaired_data)
            outlier_count = outliers.sum()
            
            if outlier_count > 0:
                if self.method == "clip":
                    q1 = repaired_data.quantile(0.25)
                    q3 = repaired_data.quantile(0.75)
                    iqr = q3 - q1
                    lower = q1 - 1.5 * iqr
                    upper = q3 + 1.5 * iqr
                    repaired_data = repaired_data.clip(lower=lower, upper=upper)
                elif self.method == "remove":
                    repaired_data = repaired_data[~outliers]
                elif self.method == "median":
                    median_value = repaired_data.median()
                    repaired_data[outliers] = median_value
                elif self.method == "mean":
                    mean_value = repaired_data.mean()
                    repaired_data[outliers] = mean_value
        
        return repaired_data, RepairResult(
            success=True,
            repair_type="outlier",
            message=f"使用 {self.method} 方法修复了 {outlier_count} 个异常值",
            repaired_count=outlier_count,
            details={"method": self.method}
        )
    
    def _detect_outliers(self, series: pd.Series) -> pd.Series:
        """检测异常值（使用Z分数）"""
        if len(series) < 3:
            return pd.Series(False, index=series.index)
        
        z_scores = np.abs((series - series.mean()) / series.std())
        return z_scores > self.z_score_threshold


class InconsistentRepair(RepairStrategy):
    """不一致数据修复策略（主要用于OHLC）"""
    
    def __init__(self):
        super().__init__("不一致数据修复")
    
    def repair(
        self,
        data: pd.DataFrame | pd.Series,
        issue: ValidationResult
    ) -> tuple[pd.DataFrame | pd.Series, RepairResult]:
        """修复不一致的OHLC数据"""
        if isinstance(data, pd.Series):
            return data, RepairResult(
                success=False,
                repair_type="inconsistent",
                message="单列数据无法修复OHLC不一致",
            )
        
        if "high" not in data.columns or "low" not in data.columns:
            return data, RepairResult(
                success=False,
                repair_type="inconsistent",
                message="缺少OHLC列",
            )
        
        repaired_data = data.copy()
        repaired_count = 0
        
        # 修复high < low的情况
        invalid_mask = repaired_data["high"] < repaired_data["low"]
        if invalid_mask.any():
            # 交换high和low
            temp = repaired_data.loc[invalid_mask, "high"].copy()
            repaired_data.loc[invalid_mask, "high"] = repaired_data.loc[invalid_mask, "low"]
            repaired_data.loc[invalid_mask, "low"] = temp
            repaired_count += invalid_mask.sum()
        
        # 修复high < open或high < close的情况
        if "open" in repaired_data.columns:
            invalid_mask = repaired_data["high"] < repaired_data["open"]
            if invalid_mask.any():
                repaired_data.loc[invalid_mask, "high"] = repaired_data.loc[invalid_mask, "open"]
                repaired_count += invalid_mask.sum()
        
        if "close" in repaired_data.columns:
            invalid_mask = repaired_data["high"] < repaired_data["close"]
            if invalid_mask.any():
                repaired_data.loc[invalid_mask, "high"] = repaired_data.loc[invalid_mask, "close"]
                repaired_count += invalid_mask.sum()
        
        # 修复low > open或low > close的情况
        if "open" in repaired_data.columns:
            invalid_mask = repaired_data["low"] > repaired_data["open"]
            if invalid_mask.any():
                repaired_data.loc[invalid_mask, "low"] = repaired_data.loc[invalid_mask, "open"]
                repaired_count += invalid_mask.sum()
        
        if "close" in repaired_data.columns:
            invalid_mask = repaired_data["low"] > repaired_data["close"]
            if invalid_mask.any():
                repaired_data.loc[invalid_mask, "low"] = repaired_data.loc[invalid_mask, "close"]
                repaired_count += invalid_mask.sum()
        
        return repaired_data, RepairResult(
            success=True,
            repair_type="inconsistent",
            message=f"修复了 {repaired_count} 条不一致的OHLC记录",
            repaired_count=repaired_count,
        )


class DataRepair:
    """数据修复器"""
    
    def __init__(self):
        """初始化数据修复器"""
        self.repair_strategies: Dict[str, RepairStrategy] = {
            "missing": MissingDataRepair(method="forward_fill"),
            "outlier": OutlierRepair(method="clip"),
            "inconsistent": InconsistentRepair(),
        }
        self.repair_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        logger.info("数据修复器初始化完成")
    
    def add_strategy(self, issue_type: str, strategy: RepairStrategy):
        """添加修复策略"""
        self.repair_strategies[issue_type] = strategy
        logger.debug(f"添加修复策略: {issue_type} - {strategy.strategy_name}")
    
    def repair(
        self,
        data: pd.DataFrame | pd.Series,
        issues: List[ValidationResult],
        ticker: str,
        auto_apply: bool = False
    ) -> tuple[pd.DataFrame | pd.Series, List[RepairResult]]:
        """
        修复数据问题

        Args:
            data: 数据
            issues: 验证问题列表
            ticker: 标的代码
            auto_apply: 是否自动应用修复（False时只返回修复后的数据，不修改原数据）

        Returns:
            (修复后的数据, 修复结果列表)
        """
        repaired_data = data.copy() if not auto_apply else data
        repair_results: List[RepairResult] = []
        
        for issue in issues:
            if issue.passed:
                continue
            
            issue_type = issue.issue_type
            
            # 映射问题类型到修复策略
            strategy_type = None
            if issue_type in ["missing_data", "missing_column"]:
                strategy_type = "missing"
            elif issue_type in ["price_range", "price_change", "volume_spike"]:
                strategy_type = "outlier"
            elif issue_type in ["ohlc_consistency"]:
                strategy_type = "inconsistent"
            
            if strategy_type and strategy_type in self.repair_strategies:
                strategy = self.repair_strategies[strategy_type]
                
                if strategy.enabled:
                    try:
                        fixed_data, result = strategy.repair(repaired_data, issue)
                        repaired_data = fixed_data
                        repair_results.append(result)
                        
                        # 记录修复历史
                        self.repair_history.append({
                            "ticker": ticker,
                            "timestamp": datetime.now().isoformat(),
                            "issue_type": issue_type,
                            "strategy": strategy_type,
                            "result": result.message,
                            "repaired_count": result.repaired_count,
                        })
                        
                        if len(self.repair_history) > self.max_history:
                            self.repair_history = self.repair_history[-self.max_history:]
                    except Exception as e:
                        logger.error(f"修复失败: {issue_type} - {e}")
                        repair_results.append(RepairResult(
                            success=False,
                            repair_type=issue_type,
                            message=f"修复失败: {e}",
                        ))
        
        return repaired_data, repair_results
    
    def get_repair_history(self, ticker: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """获取修复历史"""
        filtered = self.repair_history
        
        if ticker:
            filtered = [r for r in filtered if r.get("ticker") == ticker]
        
        return filtered[-limit:] if limit > 0 else filtered

