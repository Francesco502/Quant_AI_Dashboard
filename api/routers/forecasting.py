"""
AI预测 API 路由
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel

from core.advanced_forecasting import quick_predict, advanced_price_forecast

router = APIRouter()


class ForecastRequest(BaseModel):
    """预测请求模型"""
    tickers: List[str]
    horizon: int = 5
    model_type: str = "xgboost"
    use_production_model: bool = True
    use_enhanced_features: bool = True


@router.post("/predict")
async def predict(request: ForecastRequest):
    """快速预测（使用生产模型）"""
    try:
        results = {}
        for ticker in request.tickers:
            pred = quick_predict(
                ticker=ticker,
                horizon=request.horizon,
                model_type=request.model_type,
                use_production_model=request.use_production_model,
                save_signal=False,
            )

            if pred is not None and not pred.empty:
                results[ticker] = {
                    "predictions": [
                        {"date": str(date), "price": float(price)}
                        for date, price in pred["prediction"].items()
                    ],
                    "horizon": request.horizon,
                }
            else:
                results[ticker] = {"error": "预测失败"}

        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")


@router.get("/predict/{ticker}")
async def predict_get(
    ticker: str,
    horizon: int = Query(5, description="预测天数"),
    model_type: str = Query("xgboost", description="模型类型"),
    use_production_model: bool = Query(True, description="是否使用生产模型"),
):
    """快速预测（GET方式）"""
    try:
        pred = quick_predict(
            ticker=ticker,
            horizon=horizon,
            model_type=model_type,
            use_production_model=use_production_model,
            save_signal=False,
        )

        if pred is None or pred.empty:
            raise HTTPException(status_code=400, detail=f"无法为 {ticker} 生成预测")

        return {
            "ticker": ticker,
            "predictions": [
                {"date": str(date), "price": float(price)}
                for date, price in pred["prediction"].items()
            ],
            "horizon": horizon,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")


@router.post("/batch-predict")
async def batch_predict(request: ForecastRequest):
    """批量预测（使用高级预测接口）"""
    try:
        from core.data_service import load_price_data

        # 加载价格数据
        price_data = load_price_data(tickers=request.tickers, days=365)

        if price_data is None or price_data.empty:
            raise HTTPException(status_code=400, detail="无法加载价格数据")

        # 执行预测
        forecast_df = advanced_price_forecast(
            price_data,
            horizon=request.horizon,
            model_type=request.model_type,
            use_enhanced_features=request.use_enhanced_features,
        )

        # 转换为字典格式
        results = {}
        for ticker in forecast_df.columns:
            results[ticker] = [
                {"date": str(date), "price": float(price)}
                for date, price in forecast_df[ticker].items()
            ]

        return {"results": results, "horizon": request.horizon}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量预测失败: {str(e)}")

