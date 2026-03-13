"""Integration tests for forecasting API endpoints."""

from unittest.mock import patch

import pandas as pd
import pytest


pytestmark = pytest.mark.integration


class TestForecastingAPI:
    @patch("api.routers.forecasting.get_available_models")
    def test_list_models(self, mock_get_available_models, auth_client):
        mock_get_available_models.return_value = {
            "XGBoost": True,
            "LightGBM": False,
            "Prophet": True,
            "ARIMA": True,
            "Random Forest": True,
            "LSTM": False,
            "GRU": False,
            "Sklearn": True,
        }

        response = auth_client.get("/api/forecasting/models")

        assert response.status_code == 200
        data = response.json()
        assert data["models"] == ["auto", "xgboost", "prophet", "arima", "random_forest", "ensemble"]
        assert data["availability"]["XGBoost"] is True

    @patch("api.routers.forecasting.quick_predict")
    def test_quick_predict(self, mock_quick_predict, auth_client):
        mock_df = pd.DataFrame(
            {"prediction": [100.0, 101.0, 102.0]},
            index=pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
        )
        mock_quick_predict.return_value = mock_df

        response = auth_client.get("/api/forecasting/predict/AAPL?horizon=3&model_type=xgboost")

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert len(data["predictions"]) == 3
        assert data["predictions"][0]["price"] == 100.0

    @patch("api.routers.forecasting.run_forecast")
    def test_advanced_predict(self, mock_run_forecast, auth_client):
        mock_run_forecast.return_value = {
            "ticker": "AAPL",
            "model": "Prophet",
            "horizon": 5,
            "predictions": [],
        }

        payload = {"tickers": ["AAPL"], "horizon": 5, "model_type": "prophet"}
        response = auth_client.post("/api/forecasting/predict", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "AAPL" in data["results"]

    def test_health_check(self, auth_client):
        response = auth_client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
