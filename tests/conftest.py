import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def client():
    # Le bloc `with` déclenche le lifespan : le modèle est chargé avant les tests
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def reservation_valide() -> dict:
    # Nouvelle copie à chaque test : un test peut la modifier sans gêner les autres
    chemin = ROOT_DIR / "data" / "exemple_reservation.json"
    return json.loads(chemin.read_text(encoding="utf-8"))
