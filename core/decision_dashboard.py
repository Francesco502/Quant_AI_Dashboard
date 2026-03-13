"""决策仪表盘模块

借鉴来源: daily_stock_analysis 项目的决策仪表盘功能

功能：
- 一句话核心结论
- 精确买卖点位
- 操作检查清单

输出格式示例：
{
    "ticker": "600519",
    " conclusion": "贵州茅台当前处于 MULTISIDE 区间，技术面偏强但估值偏高，建议观望等待回调机会。",
    "action": "观望",
    "score": 65,
    "buy_price": 1750.0,
    "stop_loss": 1650.0,
    "target_price": 1900.0,
    "checklist": [
        {"condition": "价格在MA20上方", "status": "满足", "value": "1780 > 1750"},
        {"condition": "RSI在中性区间", "status": "满足", "value": "RSI=55"},
        {"condition": "MACD金叉", "status": "满足", "value": "MACD线在信号线上方"}
    ],
    "highlights": ["质地优良的消费龙头"],
    "risks": ["估值偏高", "消费 enum 情绪偏弱"]
}
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import logging

from core.data_service import load_price_data
from core.risk_analysis import calculate_max_drawdown, calculate_var, calculate_cvar
from core.advanced_forecasting import run_forecast


logger = logging.getLogger(__name__)


class DecisionDashboard:
    """决策仪表盘"""

    def __init__(self, ticker: str, days: int = 365):
        """
        初始化决策仪表盘

        Args:
            ticker: 股票代码
            days: 分析历史数据天数
        """
        self.ticker = ticker
        self.days = days
        self.price_df = None
        self.returns = None
        self.indicators = None

    def _load_data(self) -> bool:
        """加载数据"""
        try:
            self.price_df = load_price_data([self.ticker], days=self.days)
            if self.price_df.empty or self.ticker not in self.price_df.columns:
                return False

            self.returns = self.price_df[self.ticker].pct_change().dropna()
            return True
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return False

    def _calculate_technical_indicators(self) -> Dict:
        """计算技术指标"""
        series = self.price_df[self.ticker].dropna()

        # 简单移动平均线
        sma_20 = series.rolling(20).mean().iloc[-1]
        sma_50 = series.rolling(50).mean().iloc[-1]
        sma_200 = series.rolling(200).mean().iloc[-1]

        # RSI（简化计算）
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]

        # MACD（简化计算）
        ema_12 = series.ewm(span=12, adjust=False).mean()
        ema_26 = series.ewm(span=26, adjust=False).mean()
        macd = ema_12 - ema_26
        macd_signal = macd.ewm(span=9, adjust=False).mean()

        # 最新价格
        last_price = series.iloc[-1]

        return {
            "last_price": float(last_price),
            "sma_20": float(sma_20),
            "sma_50": float(sma_50),
            "sma_200": float(sma_200),
            "rsi": float(rsi),
            "macd": float(macd.iloc[-1]),
            "macd_signal": float(macd_signal.iloc[-1]),
        }

    def _generate_signals(self, indicators: Dict) -> Dict:
        """生成交易信号"""
        rsi = indicators["rsi"]
        last_price = indicators["last_price"]
        sma_20 = indicators["sma_20"]
        sma_50 = indicators["sma_50"]
        macd = indicators["macd"]
        macd_signal = indicators["macd_signal"]

        # 计算各指标得分
        rsi_score = 0
        if rsi < 30:
            rsi_score = 1.0  # 超卖
        elif rsi > 70:
            rsi_score = -1.0  # 超买
        else:
            rsi_score = (rsi - 50) / 50 * 0.5  # 中性区间

        trend_score = 0
        if sma_20 > sma_50 and sma_50 > sma_200:
            trend_score = 1.0  # 多头排列
        elif sma_20 < sma_50 and sma_50 < sma_200:
            trend_score = -1.0  # 空头排列
        else:
            trend_score = 0.3 if sma_20 > sma_50 else -0.3

        macd_score = 1.0 if macd > macd_signal else -1.0

        # 综合得分
        combined_score = (rsi_score * 0.3 + trend_score * 0.5 + macd_score * 0.2)
        score = int((combined_score + 1) / 2 * 100)  # 转换为 0-100

        # 确定动作
        if score >= 80:
            action = "强烈买入"
        elif score >= 60:
            action = "买入"
        elif score <= 20:
            action = "强烈卖出"
        elif score <= 40:
            action = "卖出"
        else:
            action = "观望"

        # 设置买卖点位
        buy_price = last_price * 0.95 if action in ["买入", "强烈买入"] else None
        stop_loss = last_price * 0.90 if buy_price else None
        target_price = last_price * 1.15 if action in ["买入", "强烈买入"] else None

        return {
            "action": action,
            "score": score,
            "buy_price": buy_price,
            "stop_loss": stop_loss,
            "target_price": target_price,
        }

    def _generate_checklist(self, indicators: Dict) -> List[Dict]:
        """生成操作检查清单"""
        checklist = []

        # 检查MA关系
        if indicators["sma_20"] > indicators["sma_50"]:
            checklist.append({
                "condition": "20日均线在50日均线上方",
                "status": "满足" if indicators["sma_20"] > indicators["sma_50"] else "不满足",
                "value": f"{indicators['sma_20']:.2f} > {indicators['sma_50']:.2f}"
            })

        # 检查RSI
        rsi = indicators["rsi"]
        rsi_status = "满足" if 40 < rsi < 60 else ("偏弱" if rsi < 40 else "偏强")
        checklist.append({
            "condition": "RSI处于中性区间(40-60)",
            "status": rsi_status,
            "value": f"RSI={rsi:.1f}"
        })

        # 检查MACD
        macd_status = "满足" if indicators["macd"] > indicators["macd_signal"] else "不满足"
        checklist.append({
            "condition": "MACD线在信号线上方",
            "status": macd_status,
            "value": f"MACD={indicators['macd']:.4f} > {indicators['macd_signal']:.4f}"
        })

        return checklist

    def _analyze_risk(self) -> Dict:
        """风险分析"""
        series = self.price_df[self.ticker].dropna()
        returns = series.pct_change().dropna()

        # 计算风险指标
        max_dd, _ = calculate_max_drawdown(series)
        var_95 = calculate_var(returns, 0.05)
        cvar_95 = calculate_cvar(returns, 0.05)
        annual_vol = float(returns.std() * np.sqrt(252))

        return {
            "max_drawdown": float(max_dd),
            "var_95": float(var_95),
            "cvar_95": float(cvar_95),
            "annual_volatility": annual_vol,
        }

    def _generate_highlights_and_risks(self, indicators: Dict, risk: Dict) -> Dict:
        """生成亮点和风险提示"""
        highlights = []
        risks = []

        # 动态风险值
        rsi = indicators["rsi"]
        last_price = indicators["last_price"]
        max_dd = risk["max_drawdown"]

        # 亮点
        if rsi < 35:
            highlights.append("RSI处于超卖区，存在反弹机会")
        if max_dd > -0.2:
            highlights.append("历史最大回撤相对温和，风险可控")

        # 风险
        if rsi > 70:
            risks.append("RSI处于超买区，存在回调风险")
        if max_dd < -0.3:
            risks.append("历史最大回撤较深（超过30%），风险较高")
        if risk["annual_volatility"] > 0.4:
            risks.append(f"年化波动率较高（{risk['annual_volatility']:.1%}），价格波动剧烈")

        return {
            "highlights": highlights if highlights else ["基本面稳定"],
            "risks": risks if risks else ["无重大风险提示"],
        }

    def analyze(self) -> Dict:
        """
        执行分析

        Returns:
            决策仪表盘结果
        """
        if not self._load_data():
            return {
                "ticker": self.ticker,
                "error": "数据加载失败",
                "timestamp": datetime.now().isoformat(),
            }

        # 1. 计算技术指标
        indicators = self._calculate_technical_indicators()

        # 2. 生成信号
        signals = self._generate_signals(indicators)

        # 3. 风险分析
        risk = self._analyze_risk()

        # 4. 生成亮点和风险
        highlights_risks = self._generate_highlights_and_risks(indicators, risk)

        # 5. 生成检查清单
        checklist = self._generate_checklist(indicators)

        # 6. 生成结论
        action = signals["action"]
        score = signals["score"]

        if action == "强烈买入":
            conclusion = f"{self.ticker} 当前处于Strong Buy区域，技术面强劲，建议逢低布局。"
        elif action == "买入":
            conclusion = f"{self.ticker} 当前处于Buy区域，技术面偏强，建议逐步建仓。"
        elif action == "卖出":
            conclusion = f"{self.ticker} 当前处于Sell区域，技术面偏弱，建议减仓观望。"
        elif action == "强烈卖出":
            conclusion = f"{self.ticker} 当前处于Strong Sell区域，技术面疲弱，建议清仓离场。"
        else:
            conclusion = f"{self.ticker} 当前处于观望区域，多空力量平衡，建议等待更明确信号。"

        return {
            "ticker": self.ticker,
            "conclusion": conclusion,
            "action": action,
            "score": score,
            "buy_price": signals["buy_price"],
            "stop_loss": signals["stop_loss"],
            "target_price": signals["target_price"],
            "checklist": checklist,
            "highlights": highlights_risks["highlights"],
            "risks": highlights_risks["risks"],
            "latest_price": indicators["last_price"],
            "latest_rsi": indicators["rsi"],
            "latest_macd": indicators["macd"],
            "risk_metrics": risk,
            "timestamp": datetime.now().isoformat(),
        }


def get_decision_dashboard(ticker: str) -> Dict:
    """
    便捷函数：获取决策仪表盘

    Args:
        ticker: 股票代码

    Returns:
        决策仪表盘结果
    """
    dashboard = DecisionDashboard(ticker)
    return dashboard.analyze()
