import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.version import VERSION


@pytest.mark.integration
def test_version_consistency():
    """版本号在核心与 API 中保持一致"""
    assert VERSION == "2.1.4"
    assert app.version == VERSION


@pytest.mark.integration
def test_health_endpoint_ok():
    """/api/health 能正常返回且结构正确"""
    client = TestClient(app)
    resp = client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()

    assert data.get("status") == "healthy"
    assert data.get("service") == "quant-ai-api"
    assert data.get("version") == VERSION

    memory = data.get("memory")
    assert isinstance(memory, dict)
    assert "total_mb" in memory
    assert "available_mb" in memory
    assert "percent" in memory
