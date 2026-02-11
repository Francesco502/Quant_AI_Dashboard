"""
AI 预测 API 集成测试
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import pandas as pd
from datetime import datetime

from api.main import app

client = TestClient(app)

class TestForecastingAPI:
    
    @patch("api.routers.forecasting.quick_predict")
    def test_quick_predict(self, mock_quick_predict):
        # 模拟 quick_predict 返回
        mock_df = pd.DataFrame({
            "prediction": [100.0, 101.0, 102.0]
        }, index=pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]))
        mock_quick_predict.return_value = mock_df
        
        response = client.get("/api/forecasting/predict/AAPL?horizon=3&model_type=xgboost")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert len(data["predictions"]) == 3
        assert data["predictions"][0]["price"] == 100.0
        
    @patch("api.routers.forecasting.run_forecast")
    def test_advanced_predict(self, mock_run_forecast):
        # 模拟 run_forecast 返回
        mock_run_forecast.return_value = {
            "ticker": "AAPL",
            "model": "Prophet",
            "horizon": 5,
            "predictions": []
        }
        
        payload = {
            "tickers": ["AAPL"],
            "horizon": 5,
            "model_type": "prophet"
        }
        
        response = client.post("/api/forecasting/predict", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "AAPL" in data["results"]
        
    def test_health_check(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
