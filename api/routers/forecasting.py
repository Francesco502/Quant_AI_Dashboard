"""Forecasting API routes."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.advanced_forecasting import (
    advanced_price_forecast,
    get_available_models,
    quick_predict,
    run_forecast,
)

router = APIRouter()


class ForecastRequest(BaseModel):
    """Forecast request payload."""

    tickers: List[str]
    horizon: int = 30
    model_type: str = "prophet"
    use_enhanced_features: bool = False


MODEL_NAME_MAPPING = {
    "XGBoost": "xgboost",
    "LightGBM": "lightgbm",
    "Prophet": "prophet",
    "ARIMA": "arima",
    "Random Forest": "random_forest",
    "LSTM": "lstm",
    "GRU": "gru",
    "Sklearn": "random_forest",
}


@router.post("/predict")
async def predict(request: ForecastRequest):
    """Run batch forecasting for one or more tickers."""

    try:
        results = {}
        for ticker in request.tickers:
            try:
                results[ticker] = run_forecast(
                    ticker=ticker,
                    horizon=request.horizon,
                    model_type=request.model_type,
                )
            except Exception as exc:  # noqa: BLE001
                results[ticker] = {"error": str(exc)}

        return {"status": "success", "results": results}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Forecast service error: {exc}") from exc


@router.get("/models")
async def list_models():
    """Return the forecast model ids the frontend can offer."""

    availability = get_available_models()
    enabled_models = {
        model_id
        for label, model_id in MODEL_NAME_MAPPING.items()
        if availability.get(label)
    }

    preferred_order = [
        "auto",
        "xgboost",
        "lightgbm",
        "prophet",
        "arima",
        "random_forest",
        "ensemble",
        "lstm",
        "gru",
    ]
    models = [
        model_name
        for model_name in preferred_order
        if model_name in {"auto", "ensemble"} or model_name in enabled_models
    ]

    return {"models": models, "availability": availability}


@router.get("/predict/{ticker}")
async def predict_get(
    ticker: str,
    horizon: int = Query(5, description="Forecast horizon in trading days."),
    model_type: str = Query("xgboost", description="Model type."),
    use_production_model: bool = Query(True, description="Whether to prefer the production model."),
    lookback_days: Optional[int] = Query(None, description="Lookback window for local data."),
):
    """Run a single-ticker forecast."""

    try:
        result = quick_predict(
            ticker=ticker,
            horizon=horizon,
            model_type=model_type,
            use_production_model=use_production_model,
            save_signal=False,
            lookback_days=lookback_days,
        )

        if result is None:
            from core.data_store import load_local_price_history

            has_data = load_local_price_history(ticker)
            if has_data is None or has_data.empty or len(has_data) < 6:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{ticker} does not have enough local price history. "
                        "Load at least 6 trading days first."
                    ),
                )
            raise HTTPException(status_code=400, detail=f"Unable to generate a forecast for {ticker}.")

        prediction_frame = result["prediction"] if isinstance(result, dict) else result
        if prediction_frame is None or prediction_frame.empty:
            raise HTTPException(status_code=400, detail=f"Unable to generate a forecast for {ticker}.")

        payload = {
            "ticker": ticker,
            "predictions": [
                {"date": str(date), "price": float(price)}
                for date, price in prediction_frame["prediction"].items()
            ],
            "horizon": horizon,
        }
        if isinstance(result, dict) and result.get("metrics"):
            payload["metrics"] = result["metrics"]
        return payload
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Forecast failed: {exc}") from exc


@router.post("/batch-predict")
async def batch_predict(request: ForecastRequest):
    """Run a multi-ticker forecast using local price history."""

    try:
        from core.data_service import load_price_data

        price_data = load_price_data(tickers=request.tickers, days=365)
        if price_data is None or price_data.empty:
            raise HTTPException(status_code=400, detail="Unable to load price data.")

        forecast_df = advanced_price_forecast(
            price_data,
            horizon=request.horizon,
            model_type=request.model_type,
            use_enhanced_features=request.use_enhanced_features,
        )

        results = {}
        for ticker in forecast_df.columns:
            results[ticker] = [
                {"date": str(date), "price": float(price)}
                for date, price in forecast_df[ticker].items()
            ]

        return {"results": results, "horizon": request.horizon}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Batch forecast failed: {exc}") from exc
