"""
账户管理 API 路由
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel

from core.account import ensure_account_dict
import os
import json

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ACCOUNT_PATH = os.path.join(BASE_DIR, "data", "accounts", "paper_account_api.json")


@router.get("/paper")
async def get_paper_account():
    """获取模拟账户信息"""
    try:
        if os.path.exists(ACCOUNT_PATH):
            with open(ACCOUNT_PATH, "r", encoding="utf-8") as f:
                account = json.load(f)
        else:
            account = None

        account = ensure_account_dict(account, initial_capital=1_000_000.0)
        return account
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取账户信息失败: {str(e)}")


@router.get("/paper/equity")
async def get_equity_history():
    """获取账户权益历史"""
    try:
        if os.path.exists(ACCOUNT_PATH):
            with open(ACCOUNT_PATH, "r", encoding="utf-8") as f:
                account = json.load(f)
        else:
            account = None

        account = ensure_account_dict(account, initial_capital=1_000_000.0)
        equity_history = account.get("equity_history", [])

        return {"equity_history": equity_history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取权益历史失败: {str(e)}")


@router.get("/paper/positions")
async def get_positions():
    """获取当前持仓"""
    try:
        if os.path.exists(ACCOUNT_PATH):
            with open(ACCOUNT_PATH, "r", encoding="utf-8") as f:
                account = json.load(f)
        else:
            account = None

        account = ensure_account_dict(account, initial_capital=1_000_000.0)
        positions = account.get("positions", {})

        return {"positions": positions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取持仓失败: {str(e)}")


@router.get("/paper/trades")
async def get_trade_log(limit: Optional[int] = None):
    """获取交易记录"""
    try:
        if os.path.exists(ACCOUNT_PATH):
            with open(ACCOUNT_PATH, "r", encoding="utf-8") as f:
                account = json.load(f)
        else:
            account = None

        account = ensure_account_dict(account, initial_capital=1_000_000.0)
        trade_log = account.get("trade_log", [])

        if limit:
            trade_log = trade_log[-limit:]

        return {"trades": trade_log, "count": len(trade_log)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易记录失败: {str(e)}")

