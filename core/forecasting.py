import numpy as np
import pandas as pd


def simple_price_forecast(price_df: pd.DataFrame, horizon: int = 3) -> pd.DataFrame:
    """Generate a lightweight trend-aware forecast from recent price history.

    Uses exponential smoothing on the most recent close prices to estimate
    a short-term trend, then projects forward with dampened momentum.
    Suitable as a fallback when no ML model is available.
    """
    if price_df.empty:
        raise ValueError("price_df is empty and cannot be forecast.")

    close_col = "close" if "close" in price_df.columns else price_df.columns[0]
    series = price_df[close_col].astype(float)

    window = min(20, len(series))
    recent = series.tail(window)

    # Simple exponential smoothing: alpha=0.3 gives moderate recency weight
    alpha = 0.3
    smoothed = recent.iloc[0]
    for v in recent.iloc[1:]:
        smoothed = alpha * v + (1 - alpha) * smoothed

    # Estimate daily drift from the last few observations
    if len(recent) >= 5:
        drift = (recent.iloc[-1] - recent.iloc[-5]) / 5
    else:
        drift = 0.0

    # Dampen drift for longer horizons to avoid extreme extrapolation
    last_value = recent.iloc[-1]
    forecasts = []
    for step in range(1, horizon + 1):
        dampened_drift = drift * (0.8 ** (step - 1))
        forecast_value = last_value + dampened_drift * step
        forecasts.append(forecast_value)

    last_date = price_df.index[-1]
    try:
        future_dates = pd.bdate_range(
            start=last_date + pd.Timedelta(days=1),
            periods=horizon,
        )
    except TypeError:
        future_dates = pd.bdate_range(
            start=last_date + pd.Timedelta(days=1),
            periods=horizon,
            closed="right",
        )

    result = pd.DataFrame({"forecast": forecasts}, index=future_dates)
    result.index.name = "date"
    return result


# Future extension point for a project-grade sequence model implementation.
# def lstm_price_forecast(price_df: pd.DataFrame, horizon: int = 3) -> pd.DataFrame:
#     """
#     Replace the demo forecast logic with an LSTM / Transformer model when
#     needed. A production implementation would:
#     - use market time-series tensors as model inputs;
#     - train for multi-step price or return forecasting;
#     - replace demo feature preparation with financial feature engineering.
#     """
#     raise NotImplementedError("Connect a real LSTM / Transformer model here.")
