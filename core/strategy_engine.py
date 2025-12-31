"""简单策略与交易信号聚合模块

阶段1目标：
- 在不引入实盘下单与持仓管理的前提下，为 Dashboard 提供一个
  “多资产选股 + 买卖信号总览”的统一接口。

设计思路：
- 复用 `technical_indicators` 中已经实现的技术指标与单资产信号逻辑；
- 对多个资产循环计算信号，并在最后一行给出当前综合信号；
- 根据综合信号的数值区间，给出文字化的交易建议（买入/卖出/观望）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional

import numpy as np
import pandas as pd

from .technical_indicators import calculate_all_indicators, get_trading_signals
from .risk_analysis import calculate_max_drawdown


@dataclass
class SignalSummary:
    """单个资产在当前时点的信号汇总"""

    ticker: str
    last_price: float
    ma_cross: float
    rsi_signal: float
    macd_signal: float
    combined_signal: float
    action: str
    rsi_value: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    reason: str | None = None
    annual_volatility: float | None = None
    max_drawdown: float | None = None


def _interpret_action(
    score: float,
    buy_threshold: float = 0.3,
    strong_buy_threshold: float = 0.7,
    sell_threshold: float = -0.3,
    strong_sell_threshold: float = -0.7,
) -> str:
    """根据综合信号数值给出文字化的交易动作建议

    阈值说明（默认与原来逻辑保持一致）：
    - strong_buy_threshold: 综合信号 >= 该值 -> 强烈买入
    - buy_threshold:       综合信号 >= 该值 -> 买入
    - sell_threshold:      综合信号 <= 该值 -> 卖出
    - strong_sell_threshold: 综合信号 <= 该值 -> 强烈卖出
    """
    if np.isnan(score):
        return "观望/数据不足"

    if score >= strong_buy_threshold:
        return "强烈买入"
    if score >= buy_threshold:
        return "买入"
    if score <= strong_sell_threshold:
        return "强烈卖出"
    if score <= sell_threshold:
        return "卖出"
    return "观望/持有"


def generate_multi_asset_signals(
    price_df: pd.DataFrame,
    min_history: int = 60,
    buy_threshold: float = 0.3,
    strong_buy_threshold: float = 0.7,
    sell_threshold: float = -0.3,
    strong_sell_threshold: float = -0.7,
) -> pd.DataFrame:
    """为多资产生成当前的技术面交易信号汇总表

    参数
    ----
    price_df : pd.DataFrame
        列为资产代码，行为日期的价格序列（通常为收盘价或净值）
    min_history : int
        生成有效信号所需的最小历史长度，过短的数据会被自动跳过

    返回
    ----
    pd.DataFrame
        每行一个资产，包含：
        - ticker           资产代码
        - last_price       最新价格
        - ma_cross         均线交叉信号
        - rsi_signal       RSI 信号
        - macd_signal      MACD 信号
        - combined_signal  综合信号（-1 ~ 1）
        - action           文本化的交易建议
        - rsi_value        最新 RSI 数值
        - sma_20 / sma_50  最新 20/50 日均线
        - reason           综合因子理由的中文说明
    """
    if price_df is None or price_df.empty:
        return pd.DataFrame()

    rows: List[Dict[str, object]] = []

    for ticker in price_df.columns:
        series = price_df[ticker].dropna()
        if series.empty or len(series) < min_history:
            # 数据太短时，技术指标容易失真，这里保守跳过
            continue

        try:
            indicators = calculate_all_indicators(series)
            signals = get_trading_signals(series, indicators)
            latest = signals.iloc[-1]

            last_price = float(series.iloc[-1])
            ma_cross = float(latest.get("ma_cross", np.nan))
            rsi_signal = float(latest.get("rsi_signal", np.nan))
            macd_sig = float(latest.get("macd_signal", np.nan))
            combined = float(latest.get("combined_signal", np.nan))

            # 细化因子信息
            rsi_value = float(indicators["rsi"].iloc[-1]) if "rsi" in indicators.columns else np.nan
            sma_20 = float(indicators["sma_20"].iloc[-1]) if "sma_20" in indicators.columns else np.nan
            sma_50 = float(indicators["sma_50"].iloc[-1]) if "sma_50" in indicators.columns else np.nan

            # 构造中文“因子理由”说明
            reason_parts: List[str] = []

            # RSI 解释
            if not np.isnan(rsi_value):
                if rsi_value < 30:
                    reason_parts.append(f"RSI≈{rsi_value:.1f}（超卖区，存在反弹机会）")
                elif rsi_value > 70:
                    reason_parts.append(f"RSI≈{rsi_value:.1f}（超买区，短期回调风险上升）")
                else:
                    reason_parts.append(f"RSI≈{rsi_value:.1f}（中性区间）")

            # 均线关系
            if not np.isnan(sma_20) and not np.isnan(sma_50):
                if sma_20 > sma_50:
                    reason_parts.append("20日均线在50日均线之上（中期趋势偏强）")
                elif sma_20 < sma_50:
                    reason_parts.append("20日均线在50日均线之下（中期趋势偏弱）")
                else:
                    reason_parts.append("20日与50日均线接近（趋势不明朗）")

            # MACD 解释
            if not np.isnan(macd_sig) and "macd" in indicators.columns and "macd_signal" in indicators.columns:
                macd_val = float(indicators["macd"].iloc[-1])
                macd_signal_val = float(indicators["macd_signal"].iloc[-1])
                if macd_val > macd_signal_val:
                    reason_parts.append("MACD 在信号线之上（动能偏多）")
                elif macd_val < macd_signal_val:
                    reason_parts.append("MACD 在信号线之下（动能偏空）")
                else:
                    reason_parts.append("MACD 与信号线接近（动能中性）")

            # 单票风险指标：年化波动率 & 最大回撤
            try:
                returns = series.pct_change().dropna()
                if len(returns) > 0:
                    annual_vol = float(returns.std() * np.sqrt(252))
                else:
                    annual_vol = np.nan
            except Exception:
                annual_vol = np.nan

            try:
                max_dd, _ = calculate_max_drawdown(series)
                max_dd = float(max_dd)
            except Exception:
                max_dd = np.nan

            if not np.isnan(annual_vol):
                if annual_vol > 0.4:
                    reason_parts.append(f"年化波动率偏高（≈{annual_vol:.1%}），价格波动较大，需注意仓位控制")
                elif annual_vol < 0.15:
                    reason_parts.append(f"年化波动率较低（≈{annual_vol:.1%}），走势相对平稳")

            if not np.isnan(max_dd):
                if max_dd < -0.3:
                    reason_parts.append(f"历史最大回撤较深（≈{max_dd:.1%}），曾出现较大下跌，风险承受能力需匹配")
                elif max_dd > -0.1:
                    reason_parts.append(f"历史最大回撤相对温和（≈{max_dd:.1%}）")

            # 综合方向总结
            action_text = _interpret_action(
                combined,
                buy_threshold=buy_threshold,
                strong_buy_threshold=strong_buy_threshold,
                sell_threshold=sell_threshold,
                strong_sell_threshold=strong_sell_threshold,
            )
            if action_text.startswith("强烈买入") or action_text == "买入":
                summary = "多项技术指标整体偏多，当前更倾向于逢低布局或加仓。"
            elif action_text.startswith("强烈卖出") or action_text == "卖出":
                summary = "技术面信号整体偏空，当前更倾向于减仓或观望。"
            elif action_text.startswith("观望"):
                summary = "多空信号相对均衡，适合继续观察等待更明确的趋势。"
            else:
                summary = ""

            if summary:
                reason_parts.append(summary)

            reason_text = "；".join(reason_parts) if reason_parts else ""

            rows.append(
                {
                    "ticker": ticker,
                    "last_price": last_price,
                    "ma_cross": ma_cross,
                    "rsi_signal": rsi_signal,
                    "macd_signal": macd_sig,
                    "combined_signal": combined,
                    "action": action_text,
                    "rsi_value": rsi_value,
                    "sma_20": sma_20,
                    "sma_50": sma_50,
                    "reason": reason_text,
                    "annual_volatility": annual_vol,
                    "max_drawdown": max_dd,
                }
            )
        except Exception:
            # 某个资产的技术指标计算失败时，不影响其他资产
            continue

    if not rows:
        return pd.DataFrame()

    df_signals = pd.DataFrame(rows)
    # 默认按综合信号从高到低排序，便于“选股”
    df_signals = df_signals.sort_values("combined_signal", ascending=False).reset_index(drop=True)
    return df_signals


