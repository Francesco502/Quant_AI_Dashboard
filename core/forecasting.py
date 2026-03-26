import numpy as np
import pandas as pd


def simple_price_forecast(price_df: pd.DataFrame, horizon: int = 3) -> pd.DataFrame:
    """Generate a lightweight demo forecast from recent average prices.

    This helper intentionally stays simple so the project can run without a
    heavy sequence model dependency. It uses the recent rolling mean as a base
    level and applies small random perturbations for each future business day.
    """
    if price_df.empty:
        raise ValueError("price_df is empty and cannot be forecast.")

    window = min(20, len(price_df))
    recent = price_df.tail(window)
    base = recent.mean(axis=0)

    last_date = price_df.index[-1]
    try:
        future_dates = pd.bdate_range(
            start=last_date + pd.Timedelta(days=1),
            periods=horizon,
        )
    except TypeError:
        # Fallback for older pandas versions that still require `closed`.
        future_dates = pd.bdate_range(
            start=last_date + pd.Timedelta(days=1),
            periods=horizon,
            closed="right",
        )

    forecasts = []
    current = base.copy()

    for _ in range(horizon):
        noise = np.random.normal(loc=0.0, scale=0.01, size=len(base))
        current = current * (1 + noise)
        forecasts.append(current.copy())

    return pd.DataFrame(forecasts, index=future_dates, columns=price_df.columns)


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
