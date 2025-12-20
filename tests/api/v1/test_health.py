# -*- coding: utf-8 -*-
"""Health API tests."""


def test_health_check(client):
    """Test health check endpoint returns healthy status."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "Chalssak"
    assert "version" in data


def test_root_endpoint(client):
    """Test root endpoint returns welcome message."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Chalssak" in data["message"]
