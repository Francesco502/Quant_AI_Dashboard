"""
数据质量检查模块
检查缺失值、异常值、数据完整性等
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from .error_handler import DashboardError, ErrorType, create_quality_error


class QualityLevel(Enum):
    """数据质量等级"""
    EXCELLENT = "优秀"
    GOOD = "良好"
    WARNING = "警告"
    ERROR = "错误"


@dataclass
class QualityReport:
    """数据质量报告"""
    ticker: str
    level: QualityLevel
    score: float  # 0-100
    issues: List[str]
    metrics: Dict[str, any]
    recommendations: List[str]


class DataQualityChecker:
    """数据质量检查器"""
    
    @staticmethod
    def check_price_data(price_series: pd.Series, ticker: str) -> QualityReport:
        """检查价格数据质量"""
        issues = []
        recommendations = []
        metrics = {}
        score = 100.0
        
        if price_series.empty:
            raise create_quality_error(ticker, "数据为空")
        
        # 1. 检查缺失值
        missing_count = price_series.isna().sum()
        missing_pct = (missing_count / len(price_series)) * 100
        metrics['missing_count'] = missing_count
        metrics['missing_pct'] = missing_pct
        
        if missing_pct > 10:
            issues.append(f"缺失值过多: {missing_pct:.1f}%")
            score -= 30
            recommendations.append("建议检查数据源或更新数据")
        elif missing_pct > 5:
            issues.append(f"存在缺失值: {missing_pct:.1f}%")
            score -= 15
            recommendations.append("建议补充缺失数据")
        
        # 2. 检查异常值（价格不应为负或零）
        negative_count = (price_series <= 0).sum()
        if negative_count > 0:
            issues.append(f"存在异常值（非正数）: {negative_count} 个")
            score -= 40
            recommendations.append("数据包含无效价格，需要清理")
        
        # 3. 检查数据连续性
        if len(price_series) > 1:
            date_index = price_series.index
            if isinstance(date_index, pd.DatetimeIndex):
                date_diffs = date_index.to_series().diff().dt.days
                # 检查是否有超过5天的间隔（可能是交易日，但周末不应超过2天）
                large_gaps = (date_diffs > 5).sum()
                if large_gaps > len(date_index) * 0.1:  # 超过10%的日期有较大间隔
                    issues.append(f"数据连续性较差: {large_gaps} 个较大间隔")
                    score -= 10
                    recommendations.append("建议检查数据完整性")
        
        # 4. 检查数据新鲜度
        if isinstance(price_series.index, pd.DatetimeIndex):
            last_date = price_series.index.max()
            days_old = (datetime.now() - last_date.to_pydatetime()).days
            metrics['days_old'] = days_old
            metrics['last_date'] = last_date
            
            if days_old > 7:
                issues.append(f"数据较旧: 最后更新于 {days_old} 天前")
                score -= 5
                recommendations.append("建议更新到最新数据")
            elif days_old > 3:
                issues.append(f"数据稍旧: 最后更新于 {days_old} 天前")
                score -= 2
        
        # 5. 检查波动率异常（价格变化过大）
        if len(price_series) > 1:
            returns = price_series.pct_change().dropna()
            if len(returns) > 0:
                volatility = returns.std()
                metrics['volatility'] = volatility
                
                # 单日涨跌幅超过50%视为异常
                extreme_returns = (returns.abs() > 0.5).sum()
                if extreme_returns > 0:
                    issues.append(f"存在极端波动: {extreme_returns} 个交易日涨跌幅超过50%")
                    score -= 20
                    recommendations.append("建议验证极端波动是否为数据错误")
        
        # 6. 检查数据量
        data_length = len(price_series)
        metrics['data_length'] = data_length
        
        if data_length < 30:
            issues.append(f"数据量不足: 仅 {data_length} 个数据点")
            score -= 15
            recommendations.append("建议获取更多历史数据以进行可靠分析")
        
        # 确定质量等级
        if score >= 90:
            level = QualityLevel.EXCELLENT
        elif score >= 75:
            level = QualityLevel.GOOD
        elif score >= 60:
            level = QualityLevel.WARNING
        else:
            level = QualityLevel.ERROR
        
        return QualityReport(
            ticker=ticker,
            level=level,
            score=max(0, score),
            issues=issues,
            metrics=metrics,
            recommendations=recommendations
        )
    
    @staticmethod
    def check_ohlcv_data(ohlcv_df: pd.DataFrame, ticker: str) -> QualityReport:
        """检查OHLCV数据质量"""
        issues = []
        recommendations = []
        metrics = {}
        score = 100.0
        
        if ohlcv_df.empty:
            raise create_quality_error(ticker, "OHLCV数据为空")
        
        required_columns = ['open', 'high', 'low', 'close']
        missing_cols = [col for col in required_columns if col not in ohlcv_df.columns]
        if missing_cols:
            raise create_quality_error(ticker, f"缺少必需列: {', '.join(missing_cols)}")
        
        # 1. 检查OHLC逻辑关系
        invalid_ohlc = (
            (ohlcv_df['high'] < ohlcv_df['low']) |
            (ohlcv_df['high'] < ohlcv_df['open']) |
            (ohlcv_df['high'] < ohlcv_df['close']) |
            (ohlcv_df['low'] > ohlcv_df['open']) |
            (ohlcv_df['low'] > ohlcv_df['close'])
        ).sum()
        
        if invalid_ohlc > 0:
            issues.append(f"OHLC逻辑错误: {invalid_ohlc} 条记录")
            score -= 30
            recommendations.append("OHLC数据不符合逻辑关系，需要修正")
        
        # 2. 检查缺失值
        for col in required_columns:
            missing_pct = (ohlcv_df[col].isna().sum() / len(ohlcv_df)) * 100
            if missing_pct > 5:
                issues.append(f"{col}列缺失值: {missing_pct:.1f}%")
                score -= 10
        
        # 3. 检查成交量
        if 'volume' in ohlcv_df.columns:
            zero_volume_pct = (ohlcv_df['volume'] == 0).sum() / len(ohlcv_df) * 100
            if zero_volume_pct > 20:
                issues.append(f"零成交量过多: {zero_volume_pct:.1f}%")
                score -= 5
        
        metrics['data_length'] = len(ohlcv_df)
        metrics['invalid_ohlc'] = invalid_ohlc
        
        # 确定质量等级
        if score >= 90:
            level = QualityLevel.EXCELLENT
        elif score >= 75:
            level = QualityLevel.GOOD
        elif score >= 60:
            level = QualityLevel.WARNING
        else:
            level = QualityLevel.ERROR
        
        return QualityReport(
            ticker=ticker,
            level=level,
            score=max(0, score),
            issues=issues,
            metrics=metrics,
            recommendations=recommendations
        )
    
    @staticmethod
    def check_dataframe_quality(df: pd.DataFrame, tickers: List[str]) -> Dict[str, QualityReport]:
        """批量检查多个资产的数据质量"""
        reports = {}
        
        for ticker in tickers:
            if ticker not in df.columns:
                continue
            
            try:
                price_series = df[ticker].dropna()
                if not price_series.empty:
                    reports[ticker] = DataQualityChecker.check_price_data(price_series, ticker)
            except Exception as e:
                # 如果检查失败，创建错误报告
                reports[ticker] = QualityReport(
                    ticker=ticker,
                    level=QualityLevel.ERROR,
                    score=0,
                    issues=[f"质量检查失败: {str(e)}"],
                    metrics={},
                    recommendations=["请检查数据源"]
                )
        
        return reports


def validate_data_before_analysis(df: pd.DataFrame, tickers: List[str], 
                                  min_data_points: int = 30) -> Tuple[bool, List[str]]:
    """在分析前验证数据，返回是否通过和警告列表"""
    warnings = []
    
    if df.empty:
        return False, ["数据框为空"]
    
    for ticker in tickers:
        if ticker not in df.columns:
            warnings.append(f"{ticker}: 数据不存在")
            continue
        
        series = df[ticker].dropna()
        if len(series) < min_data_points:
            warnings.append(f"{ticker}: 数据点不足（{len(series)} < {min_data_points}）")
    
    return len(warnings) == 0, warnings

