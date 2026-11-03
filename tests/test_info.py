"""Tests de la route /info."""

import joblib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_info_decrit_le_modele(client):
    corps = client.get("/info").json()
    assert corps["model_name"] == "cancellation_model"
    assert corps["algorithm"] == "HistGradientBoostingClassifier"
    assert corps["scikit_learn_version"] == "1.6.1"


def test_info_annonce_les_colonnes_du_modele(client):
    # Les colonnes annoncées doivent être celles que le modèle attend vraiment
    model = joblib.load(ROOT_DIR / "model" / "cancellation_model.joblib")
    assert client.get("/info").json()["features"] == list(model.feature_names_in_)


def test_info_expose_les_metriques(client):
    metriques = client.get("/info").json()["test_metrics"]
    assert set(metriques) == {"accuracy", "f1", "roc_auc"}
    assert all(0.0 <= valeur <= 1.0 for valeur in metriques.values())
