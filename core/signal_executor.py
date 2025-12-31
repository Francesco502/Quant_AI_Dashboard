"""
信号执行引擎模块（阶段四：完整信号执行闭环）

职责：
- 信号到订单的转换
- 风控检查
- 订单生成和执行
- 信号状态管理
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .signal_store import get_signal_store
from .trading_engine import apply_equal_weight_rebalance
from .data_service import load_price_data
from .account import ensure_account_dict


class RiskChecker:
    """风控检查器"""

    def __init__(
        self,
        max_single_position_pct: float = 0.2,
        max_total_exposure: float = 1.0,
        min_confidence: float = 0.5,
        max_daily_trades: int = 10,
    ):
        """
        初始化风控检查器

        参数:
            max_single_position_pct: 单票最大仓位比例
            max_total_exposure: 最大总敞口
            min_confidence: 最小置信度
            max_daily_trades: 每日最大交易次数
        """
        self.max_single_position_pct = max_single_position_pct
        self.max_total_exposure = max_total_exposure
        self.min_confidence = min_confidence
        self.max_daily_trades = max_daily_trades

    def check_signal(
        self,
        signal: Dict,
        current_positions: Dict[str, int],
        total_capital: float,
        daily_trade_count: int = 0,
    ) -> Tuple[bool, str]:
        """
        检查单个信号是否通过风控

        参数:
            signal: 信号字典
            current_positions: 当前持仓
            total_capital: 总资金
            daily_trade_count: 今日交易次数

        返回:
            (是否通过, 原因)
        """
        ticker = signal.get("ticker")
        confidence = signal.get("confidence", 0)
        direction = signal.get("direction", 0)
        target_weight = signal.get("target_weight", 0)

        # 检查置信度
        if confidence < self.min_confidence:
            return False, f"置信度不足 ({confidence:.2%} < {self.min_confidence:.2%})"

        # 检查每日交易次数
        if daily_trade_count >= self.max_daily_trades:
            return False, f"达到每日最大交易次数限制 ({self.max_daily_trades})"

        # 检查单票仓位
        if target_weight > self.max_single_position_pct:
            return False, f"单票仓位超限 ({target_weight:.2%} > {self.max_single_position_pct:.2%})"

        # 检查总敞口（简化处理，假设所有持仓都是目标权重）
        if direction != 0:  # 有交易方向
            current_exposure = sum(
                abs(target_weight) for ticker in current_positions.keys()
            )
            if current_exposure + abs(target_weight) > self.max_total_exposure:
                return False, f"总敞口超限"

        return True, "通过"

    def check_signals_batch(
        self,
        signals: pd.DataFrame,
        current_positions: Dict[str, int],
        total_capital: float,
        daily_trade_count: int = 0,
    ) -> pd.DataFrame:
        """
        批量检查信号

        参数:
            signals: 信号DataFrame
            current_positions: 当前持仓
            total_capital: 总资金
            daily_trade_count: 今日交易次数

        返回:
            添加了risk_check列和risk_reason列的信号DataFrame
        """
        if signals.empty:
            return signals

        result = signals.copy()
        result["risk_check"] = False
        result["risk_reason"] = ""

        for idx, row in result.iterrows():
            signal_dict = row.to_dict()
            passed, reason = self.check_signal(
                signal_dict, current_positions, total_capital, daily_trade_count
            )
            result.loc[idx, "risk_check"] = passed
            result.loc[idx, "risk_reason"] = reason

        return result


class SignalExecutor:
    """信号执行器"""

    def __init__(
        self,
        account_path: Optional[str] = None,
        risk_checker: Optional[RiskChecker] = None,
    ):
        """
        初始化信号执行器

        参数:
            account_path: 账户文件路径
            risk_checker: 风控检查器（None则使用默认）
        """
        self.account_path = account_path
        self.risk_checker = risk_checker or RiskChecker()
        self.signal_store = get_signal_store()

    def load_account(self, initial_capital: float = 1_000_000.0) -> Dict:
        """加载账户"""
        if self.account_path and os.path.exists(self.account_path):
            import json
            with open(self.account_path, "r", encoding="utf-8") as f:
                account = json.load(f)
        else:
            account = None

        return ensure_account_dict(account, initial_capital=initial_capital)

    def save_account(self, account: Dict) -> None:
        """保存账户"""
        if self.account_path:
            import json
            import os
            os.makedirs(os.path.dirname(self.account_path), exist_ok=True)
            with open(self.account_path, "w", encoding="utf-8") as f:
                json.dump(account, f, ensure_ascii=False, indent=2)

    def execute_signals(
        self,
        signals: pd.DataFrame,
        strategy_id: str,
        total_capital: float,
        max_positions: int = 5,
        price_data: Optional[pd.DataFrame] = None,
        tickers: Optional[List[str]] = None,
    ) -> Tuple[Dict, str, pd.DataFrame]:
        """
        执行信号

        参数:
            signals: 信号DataFrame
            strategy_id: 策略ID
            total_capital: 总资金
            max_positions: 最大持仓数
            price_data: 价格数据（None则自动加载）
            tickers: 标的列表（用于加载价格数据）

        返回:
            (账户字典, 执行结果消息, 执行详情DataFrame)
        """
        if signals.empty:
            return {}, "无信号可执行", pd.DataFrame()

        # 加载账户
        account = self.load_account(initial_capital=total_capital)
        account["initial_capital"] = total_capital

        # 加载价格数据
        if price_data is None and tickers:
            price_data = load_price_data(tickers=tickers, days=365)

        if price_data is None or price_data.empty:
            return account, "无法加载价格数据", pd.DataFrame()

        # 风控检查
        current_positions = account.get("positions", {}) or {}
        daily_trade_count = len(
            [
                log
                for log in account.get("trade_log", [])
                if log.get("date") == datetime.now().strftime("%Y-%m-%d")
            ]
        )

        signals_checked = self.risk_checker.check_signals_batch(
            signals, current_positions, total_capital, daily_trade_count
        )

        # 过滤通过风控的信号
        signals_passed = signals_checked[signals_checked["risk_check"] == True].copy()

        if signals_passed.empty:
            return (
                account,
                "所有信号均未通过风控检查",
                signals_checked[["ticker", "action", "risk_reason"]],
            )

        # 转换为交易引擎需要的格式
        signal_table = self._convert_to_signal_table(signals_passed, price_data)

        # 执行交易
        account, msg = apply_equal_weight_rebalance(
            account=account,
            signal_table=signal_table,
            data=price_data,
            total_capital=total_capital,
            max_positions=max_positions,
        )

        # 保存账户
        self.save_account(account)

        # 更新信号状态
        for _, row in signals_passed.iterrows():
            ticker = row["ticker"]
            model_id = row.get("model_id", "unknown")
            today = datetime.now().strftime("%Y-%m-%d")
            self.signal_store.update_signal_status(
                ticker=ticker, model_id=model_id, date=today, new_status="executed"
            )

        # 构建执行详情
        execution_details = signals_checked.copy()
        execution_details["executed"] = execution_details["risk_check"]

        return account, msg, execution_details

    def _convert_to_signal_table(
        self, signals: pd.DataFrame, price_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        将策略信号转换为交易引擎需要的信号表格式

        参数:
            signals: 策略信号DataFrame
            price_data: 价格数据

        返回:
            信号表DataFrame
        """
        rows = []

        for _, row in signals.iterrows():
            ticker = row["ticker"]
            action = row.get("action", "持有")
            signal_value = row.get("signal", 0)

            # 获取最新价格
            if ticker in price_data.columns:
                last_price = float(price_data[ticker].iloc[-1])
            else:
                continue

            # 转换为交易引擎格式
            # 需要combined_signal字段
            combined_signal = signal_value

            # 确定action文本
            if action in ["买入", "强烈买入"]:
                action_text = "买入" if signal_value < 0.7 else "强烈买入"
            elif action in ["卖出", "强烈卖出"]:
                action_text = "卖出" if signal_value > -0.7 else "强烈卖出"
            else:
                action_text = "观望/持有"

            rows.append({
                "ticker": ticker,
                "last_price": last_price,
                "combined_signal": combined_signal,
                "action": action_text,
                "reason": row.get("reason", ""),
            })

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)

    def get_execution_summary(
        self, signals: pd.DataFrame, execution_details: pd.DataFrame
    ) -> Dict:
        """
        获取执行摘要

        参数:
            signals: 原始信号DataFrame
            execution_details: 执行详情DataFrame

        返回:
            摘要字典
        """
        total = len(signals)
        passed = len(execution_details[execution_details["risk_check"] == True])
        executed = len(execution_details[execution_details["executed"] == True])
        rejected = total - passed

        return {
            "total_signals": total,
            "passed_risk_check": passed,
            "executed": executed,
            "rejected": rejected,
            "rejection_rate": rejected / total if total > 0 else 0,
        }


# 全局单例
_signal_executor_instance: Optional[SignalExecutor] = None


def get_signal_executor(account_path: Optional[str] = None) -> SignalExecutor:
    """获取信号执行器单例"""
    global _signal_executor_instance
    if _signal_executor_instance is None:
        _signal_executor_instance = SignalExecutor(account_path=account_path)
    return _signal_executor_instance

