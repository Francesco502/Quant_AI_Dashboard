"""
信号管理 API 路由
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from core.signal_store import get_signal_store

router = APIRouter()


class SignalResponse(BaseModel):
    """信号响应模型"""
    timestamp: str
    ticker: str
    model_id: str
    prediction: float
    direction: int
    confidence: float
    signal: str
    status: str


@router.get("/", response_model=List[Dict])
async def list_signals(
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)"),
    ticker: Optional[str] = Query(None, description="标的代码"),
    model_id: Optional[str] = Query(None, description="模型ID"),
    status: Optional[str] = Query(None, description="状态 (pending/executed/expired)"),
    days: int = Query(7, description="最近N天"),
):
    """获取信号列表"""
    try:
        signal_store = get_signal_store()

        if date:
            signals_df = signal_store.load_signals(
                date=date, ticker=ticker, model_id=model_id, status=status
            )
        else:
            signals_df = signal_store.get_latest_signals(ticker=ticker, n_days=days)
            if status:
                signals_df = signals_df[signals_df["status"] == status]

        if signals_df.empty:
            return []

        # 转换为字典列表
        signals_list = signals_df.to_dict("records")
        # 处理时间戳
        for signal in signals_list:
            if "timestamp" in signal and isinstance(signal["timestamp"], datetime):
                signal["timestamp"] = signal["timestamp"].isoformat()

        return signals_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取信号列表失败: {str(e)}")


@router.get("/latest", response_model=List[Dict])
async def get_latest_signals(
    ticker: Optional[str] = None,
    n_days: int = Query(1, description="最近N天"),
):
    """获取最新信号"""
    try:
        signal_store = get_signal_store()
        signals_df = signal_store.get_latest_signals(ticker=ticker, n_days=n_days)

        if signals_df.empty:
            return []

        signals_list = signals_df.to_dict("records")
        for signal in signals_list:
            if "timestamp" in signal and isinstance(signal["timestamp"], datetime):
                signal["timestamp"] = signal["timestamp"].isoformat()

        return signals_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最新信号失败: {str(e)}")


@router.put("/{ticker}/status")
async def update_signal_status(
    ticker: str,
    model_id: str,
    date: str,
    new_status: str,
):
    """更新信号状态"""
    try:
        signal_store = get_signal_store()
        success = signal_store.update_signal_status(ticker, model_id, date, new_status)
        if not success:
            raise HTTPException(status_code=404, detail="信号不存在")
        return {"status": "success", "message": "信号状态已更新"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新信号状态失败: {str(e)}")


@router.get("/stats")
async def get_signal_stats(
    days: int = Query(7, description="统计最近N天"),
):
    """获取信号统计信息"""
    try:
        signal_store = get_signal_store()
        signals_df = signal_store.get_latest_signals(n_days=days)

        if signals_df.empty:
            return {
                "total": 0,
                "pending": 0,
                "executed": 0,
                "expired": 0,
                "by_direction": {"buy": 0, "sell": 0, "hold": 0},
            }

        total = len(signals_df)
        pending = len(signals_df[signals_df["status"] == "pending"])
        executed = len(signals_df[signals_df["status"] == "executed"])
        expired = len(signals_df[signals_df["status"] == "expired"])

        buy_count = len(signals_df[signals_df["direction"] > 0])
        sell_count = len(signals_df[signals_df["direction"] < 0])
        hold_count = len(signals_df[signals_df["direction"] == 0])

        return {
            "total": total,
            "pending": pending,
            "executed": executed,
            "expired": expired,
            "by_direction": {
                "buy": buy_count,
                "sell": sell_count,
                "hold": hold_count,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取信号统计失败: {str(e)}")

