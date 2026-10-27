import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    # Le bloc `with` déclenche le lifespan : le modèle est chargé avant les tests
    with TestClient(app) as test_client:
        yield test_client
