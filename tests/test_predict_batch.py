"""Tests de la route /predict/batch."""

import pytest


def test_batch_renvoie_une_prediction_par_reservation(client, reservation_valide):
    lot = [reservation_valide, dict(reservation_valide, hotel="City Hotel")]
    response = client.post("/predict/batch", json={"reservations": lot})
    assert response.status_code == 200
    assert len(response.json()["predictions"]) == 2


def test_batch_donne_le_meme_resultat_qu_un_appel_unitaire(client, reservation_valide):
    unitaire = client.post("/predict", json=reservation_valide).json()
    lot = client.post("/predict/batch", json={"reservations": [reservation_valide]}).json()
    assert lot["predictions"][0]["probabilite_annulation"] == pytest.approx(
        unitaire["probabilite_annulation"], abs=1e-12
    )


def test_batch_respecte_l_ordre_des_reservations(client, reservation_valide):
    # Sans parking la probabilité grimpe : les deux réponses doivent différer
    # dans l'ordre d'envoi, pas l'inverse
    lot = [reservation_valide, dict(reservation_valide, required_car_parking_spaces=0)]
    predictions = client.post("/predict/batch", json={"reservations": lot}).json()["predictions"]
    assert predictions[0]["probabilite_annulation"] < predictions[1]["probabilite_annulation"]


@pytest.mark.parametrize("nombre", [0, 501])
def test_batch_refuse_une_taille_hors_bornes(client, reservation_valide, nombre):
    lot = [reservation_valide] * nombre
    assert client.post("/predict/batch", json={"reservations": lot}).status_code == 422


def test_batch_refuse_le_lot_si_une_reservation_est_invalide(client, reservation_valide):
    lot = [reservation_valide, dict(reservation_valide, adults=-3)]
    assert client.post("/predict/batch", json={"reservations": lot}).status_code == 422
