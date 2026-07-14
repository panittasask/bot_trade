from fastapi.testclient import TestClient

from app.main import app


def test_status_and_config_validation():
    with TestClient(app) as client:
        status = client.get("/api/status")
        assert status.status_code == 200
        assert status.json()["mode"] == "PAPER / SYNTHETIC"

        invalid = client.put(
            "/api/config",
            json={
                "short_window": 30,
                "long_window": 10,
                "trade_size_pct": 10,
                "max_position_pct": 30,
                "stop_loss_pct": 4,
                "take_profit_pct": 8,
            },
        )
        assert invalid.status_code == 422


def test_rejects_unknown_symbol():
    with TestClient(app) as client:
        response = client.put("/api/symbol", json={"symbol": "NOT-A-MARKET"})
        assert response.status_code == 400

