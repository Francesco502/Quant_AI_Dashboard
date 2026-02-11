"""
交易执行 API 路由
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
import pandas as pd

from core.signal_executor import get_signal_executor
from core.data_service import load_price_data
from core.paper_account import PaperAccount, InsufficientFundsError, InsufficientSharesError

router = APIRouter()

# --- Request Models ---

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

class TradeOrderRequest(BaseModel):
    account_id: Optional[int] = None
    ticker: str
    action: str  # BUY / SELL
    shares: int
    price: Optional[float] = None # Limit price, or None for Market price

class CreateAccountRequest(BaseModel):
    name: str
    initial_balance: float = 100000.0

# --- Paper Trading API ---

@router.post("/paper/account")
async def create_paper_account(request: CreateAccountRequest):
    """创建新的模拟账户"""
    try:
        # TODO: Get real user_id from auth context
        user_id = 1 
        account = PaperAccount(user_id=user_id)
        account_id = account.create_account(request.name, request.initial_balance)
        return {"status": "success", "account_id": account_id, "message": "账户创建成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/paper/account")
async def get_paper_account_info(account_id: Optional[int] = None):
    """获取模拟账户详情（资金、持仓、市值）"""
    try:
        user_id = 1
        account = PaperAccount(user_id=user_id, account_id=account_id)
        if not account_id:
            if not account.load_default_account():
                return {"status": "empty", "message": "未找到默认账户"}
        else:
            account._load_account()
            
        portfolio = account.get_portfolio_value()
        return {
            "status": "success",
            "account_id": account.account_id,
            "account_name": account.account_name,
            "currency": account.currency,
            "portfolio": portfolio
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/paper/order")
async def place_paper_order(request: TradeOrderRequest):
    """模拟交易下单"""
    try:
        user_id = 1
        account = PaperAccount(user_id=user_id, account_id=request.account_id)
        
        # If account_id not provided, try default
        if not request.account_id:
            if not account.load_default_account():
                 raise HTTPException(status_code=400, detail="未指定账户且无默认账户")
        else:
            account._load_account()
            
        if request.action.upper() == "BUY":
            result = account.buy(request.ticker, request.shares, request.price)
        elif request.action.upper() == "SELL":
            result = account.sell(request.ticker, request.shares, request.price)
        else:
            raise HTTPException(status_code=400, detail="不支持的交易动作")
            
        return result
    except InsufficientFundsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientSharesError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/paper/history")
async def get_trade_history(account_id: Optional[int] = None, limit: int = 50):
    """获取交易历史"""
    try:
        user_id = 1
        account = PaperAccount(user_id=user_id, account_id=account_id)
        if not account_id:
            if not account.load_default_account():
                return []
        
        return account.get_trade_history(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/paper/settlement")
async def run_daily_settlement(account_id: Optional[int] = None):
    """执行日终结算（记录权益快照）"""
    try:
        user_id = 1
        account = PaperAccount(user_id=user_id, account_id=account_id)
        if not account_id:
            if not account.load_default_account():
                return {"status": "empty", "message": "未找到默认账户"}
        else:
            account._load_account()

        result = account.daily_settlement()
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paper/equity")
async def get_equity_history(account_id: Optional[int] = None, days: int = 90):
    """获取权益曲线历史"""
    try:
        user_id = 1
        account = PaperAccount(user_id=user_id, account_id=account_id)
        if not account_id:
            if not account.load_default_account():
                return {"equity_history": []}
        
        history = account.get_equity_history(days)
        return {"equity_history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Original Execution API (Legacy/Stateless) ---

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

