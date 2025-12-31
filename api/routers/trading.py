"""
交易执行 API 路由
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict
from pydantic import BaseModel

from core.signal_executor import get_signal_executor
from core.data_service import load_price_data
from typing import Optional

router = APIRouter()


class ExecuteSignalsRequest(BaseModel):
    """执行信号请求模型"""
    signals: List[Dict]
    strategy_id: str
    total_capital: float = 1000000.0
    max_positions: int = 5
    tickers: List[str]
    data_sources: List[str] = ["AkShare"]
    alpha_vantage_key: Optional[str] = None
    tushare_token: Optional[str] = None


@router.post("/execute")
async def execute_signals(request: ExecuteSignalsRequest):
    """执行信号"""
    try:
        signal_executor = get_signal_executor()

        # 加载价格数据
        price_data = load_price_data(
            tickers=request.tickers,
            days=365,
            data_sources=request.data_sources,
            alpha_vantage_key=request.alpha_vantage_key,
            tushare_token=request.tushare_token,
        )

        if price_data is None or price_data.empty:
            raise HTTPException(status_code=400, detail="无法加载价格数据")

        import pandas as pd

        signals_df = pd.DataFrame(request.signals)

        # 执行信号
        account, msg, details = signal_executor.execute_signals(
            signals=signals_df,
            strategy_id=request.strategy_id,
            total_capital=request.total_capital,
            max_positions=request.max_positions,
            price_data=price_data,
            tickers=request.tickers,
        )

        # 获取执行摘要
        summary = signal_executor.get_execution_summary(signals_df, details)

        return {
            "status": "success",
            "message": msg,
            "summary": summary,
            "account": account,
            "details": details.to_dict("records") if not details.empty else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行信号失败: {str(e)}")


@router.get("/risk-check")
async def risk_check_signal(
    ticker: str,
    prediction: float,
    direction: int,
    confidence: float,
    target_weight: float = 0.0,
):
    """风控检查单个信号"""
    try:
        from core.signal_executor import RiskChecker

        risk_checker = RiskChecker()
        signal = {
            "ticker": ticker,
            "prediction": prediction,
            "direction": direction,
            "confidence": confidence,
            "target_weight": target_weight,
        }

        passed, reason = risk_checker.check_signal(
            signal, current_positions={}, total_capital=1000000.0, daily_trade_count=0
        )

        return {"passed": passed, "reason": reason}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"风控检查失败: {str(e)}")

