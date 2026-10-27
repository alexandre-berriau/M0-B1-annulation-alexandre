def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_loaded": True}


def test_openapi_documentation_is_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/predict" in response.json()["paths"]
