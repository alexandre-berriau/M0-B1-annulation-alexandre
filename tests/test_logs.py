"""Tests de la route /logs, qui alimente l'interface web."""


def test_logs_renvoie_une_liste_de_lignes(client):
    response = client.get("/logs")
    assert response.status_code == 200
    lignes = response.json()["lignes"]
    assert isinstance(lignes, list)
    assert all(isinstance(ligne, str) for ligne in lignes)


def test_logs_contient_le_dernier_appel(client, reservation_valide):
    client.post("/predict", json=reservation_valide)
    lignes = client.get("/logs?lignes=20").json()["lignes"]
    assert any("/predict" in ligne for ligne in lignes)


def test_logs_respecte_la_borne_demandee(client):
    assert len(client.get("/logs?lignes=5").json()["lignes"]) <= 5


def test_logs_refuse_une_borne_hors_limites(client):
    assert client.get("/logs?lignes=9999").status_code == 422
