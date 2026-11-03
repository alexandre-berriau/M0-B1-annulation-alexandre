"""Tests de la route /predict."""

from pathlib import Path

import joblib
import pandas as pd
import pytest

from app.schemas import Booking

ROOT_DIR = Path(__file__).resolve().parent.parent
CHAMPS = list(Booking.model_fields)  # les 15 colonnes, sans les recopier ici


def reservations_du_csv(nombre: int) -> list[dict]:
    # dropna() : 4 lignes sur 1 000 n'ont pas de pays et seraient refusées en 422
    chemin = ROOT_DIR / "data" / "hotel_bookings_sample.csv"
    lignes = pd.read_csv(chemin)[CHAMPS].dropna()
    lignes["children"] = lignes["children"].astype(int)
    # sample plutôt que head : les premières lignes sont toutes des Resort en juillet.
    # random_state fige le tirage, sinon les tests changeraient à chaque exécution.
    return lignes.sample(nombre, random_state=42).to_dict(orient="records")


def test_cas_valide(client, reservation_valide):
    response = client.post("/predict", json=reservation_valide)
    assert response.status_code == 200
    corps = response.json()
    assert isinstance(corps["annulation"], bool)
    assert 0.0 <= corps["probabilite_annulation"] <= 1.0


def test_prediction_coherente_avec_la_probabilite(client, reservation_valide):
    corps = client.post("/predict", json=reservation_valide).json()
    assert corps["annulation"] == (corps["probabilite_annulation"] >= 0.5)


@pytest.mark.parametrize(
    "champ, valeur",
    [
        ("hotel", "Chalet des Alpes"),
        ("arrival_date_month", "Brumaire"),
        ("deposit_type", "Gratuit"),
        ("adults", -3),
        ("adr", -10.0),
        ("country", "fra"),
        ("lead_time", "beaucoup"),
    ],
)
def test_valeur_invalide_renvoie_422(client, reservation_valide, champ, valeur):
    reservation_valide[champ] = valeur
    assert client.post("/predict", json=reservation_valide).status_code == 422


@pytest.mark.parametrize("champ", ["hotel", "adr", "country"])
def test_champ_manquant_renvoie_422(client, reservation_valide, champ):
    del reservation_valide[champ]
    assert client.post("/predict", json=reservation_valide).status_code == 422


def test_champ_inconnu_renvoie_422(client, reservation_valide):
    reservation_valide["numero_chambre"] = 404
    assert client.post("/predict", json=reservation_valide).status_code == 422


def test_le_service_repond_encore_apres_un_422(client, reservation_valide):
    client.post("/predict", json=dict(reservation_valide, adults=-3))
    assert client.get("/health").json() == {"status": "ok", "model_loaded": True}


@pytest.mark.parametrize("hotel", ["City Hotel", "Resort Hotel"])
def test_les_deux_hotels_sont_acceptes(client, reservation_valide, hotel):
    reservation_valide["hotel"] = hotel
    response = client.post("/predict", json=reservation_valide)
    assert response.status_code == 200
    assert 0.0 <= response.json()["probabilite_annulation"] <= 1.0


@pytest.mark.parametrize(
    "reservation",
    reservations_du_csv(5),
    ids=lambda r: f"{r['hotel'].split()[0]}-{r['country']}-{r['arrival_date_month'][:3]}",
)
def test_reservations_reelles_du_csv(client, reservation):
    response = client.post("/predict", json=reservation)
    assert response.status_code == 200
    assert 0.0 <= response.json()["probabilite_annulation"] <= 1.0


def test_meme_probabilite_que_le_modele_appele_en_direct(client, reservation_valide):
    # On ne teste pas que le modèle a raison, mais que l'API ne déforme rien
    model = joblib.load(ROOT_DIR / "model" / "cancellation_model.joblib")
    ligne = pd.DataFrame([reservation_valide])[list(model.feature_names_in_)]
    attendue = model.predict_proba(ligne)[0, 1]
    obtenue = client.post("/predict", json=reservation_valide).json()["probabilite_annulation"]
    assert obtenue == pytest.approx(attendue, abs=1e-9)
