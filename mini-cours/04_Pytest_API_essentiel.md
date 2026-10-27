# 04 — pytest : l'essentiel pour tester une API


## 1. Pourquoi tester ?

Demain, tu modifies le schéma pour ajouter un champ. Est-ce que `/predict` fonctionne toujours ? Est-ce qu'une valeur négative est toujours refusée ? Plutôt que de tout revérifier à la main dans Swagger, tu lances **une commande**, et en quelques secondes tu le sais.

Les tests sont aussi une **documentation vivante** : ils montrent ce que l'API doit faire et refuser. Au module 5, ils tourneront automatiquement à chaque modification du code, avant tout déploiement.

## 2. pytest en bref

Un test est une fonction dont le nom commence par `test_`, rangée dans un fichier `test_*.py`. Elle vérifie des choses avec `assert` :

```python
def test_addition():
    assert 1 + 1 == 2
```

```bash
pytest          # lance tous les tests trouvés
pytest -v       # un résultat par test (verbose)
pytest -k predict   # seulement les tests dont le nom contient "predict"
pytest -x       # s'arrêter au premier échec
```

Quand un `assert` échoue, pytest affiche les valeurs comparées : lis-les, elles disent presque toujours ce qui ne va pas.

## 3. Tester une API sans lancer de serveur : `TestClient`

FastAPI fournit un client qui envoie des requêtes à ton application **directement en mémoire**, sans uvicorn ni réseau :

```python
from fastapi.testclient import TestClient

from app.main import app

with TestClient(app) as client:
    response = client.get("/health")
    print(response.status_code)   # 200
    print(response.json())        # {'status': 'ok', 'model_loaded': True}
```

Le `with` est **indispensable** : c'est lui qui déclenche le `lifespan`, donc le chargement du modèle. Sans `with`, le modèle n'est jamais chargé.

Pour un `POST` avec un corps JSON :

```python
response = client.post("/predict", json={"hotel": "City Hotel", ...})
```

## 4. Les *fixtures* : préparer une fois, réutiliser partout

Une **fixture** est une fonction qui prépare quelque chose dont les tests ont besoin. Un test la reçoit simplement en la nommant comme paramètre :

```python
import pytest


@pytest.fixture
def chambre_valide():
    return {"type_chambre": "double", "nb_personnes": 2, "prix_nuit": 89.0}


def test_estimer(client, chambre_valide):        # pytest injecte les deux fixtures
    response = client.post("/estimer", json=chambre_valide)
    assert response.status_code == 200
```

Les fixtures placées dans `tests/conftest.py` sont disponibles dans **tous** les fichiers de tests, sans import. Le squelette de M0-B1 y fournit déjà la fixture `client`.

Une fixture renvoie une **nouvelle copie** à chaque test : tu peux modifier `chambre_valide` dans un test sans affecter les autres.

## 5. Les tests paramétrés : un test, plusieurs cas

Plutôt que d'écrire 5 tests presque identiques :

```python
@pytest.mark.parametrize("nb_personnes", [-1, 0, 7, 100])
def test_nb_personnes_invalide(client, chambre_valide, nb_personnes):
    chambre_valide["nb_personnes"] = nb_personnes
    response = client.post("/estimer", json=chambre_valide)
    assert response.status_code == 422
```

pytest exécute le test **4 fois**, une par valeur, et affiche chaque cas séparément. On peut paramétrer plusieurs arguments à la fois :

```python
@pytest.mark.parametrize("champ, valeur", [("type_chambre", "cabane"), ("prix_nuit", -10)])
def test_valeur_invalide(client, chambre_valide, champ, valeur):
    chambre_valide[champ] = valeur
    assert client.post("/estimer", json=chambre_valide).status_code == 422
```

## 6. Que tester sur une API de prédiction ?

| Type de test | Exemple | Ce qu'on vérifie |
|---|---|---|
| **Cas nominal** | une réservation valide | code 200, champs présents, types et plages corrects |
| **Cas d'erreur** | valeur inconnue, négative, champ manquant | code 422, et le service répond toujours ensuite |
| **Cohérence** | prédiction et probabilité | `annulation == (probabilite >= 0.5)` |
| **Fidélité au modèle** | une ligne réelle du jeu de données | l'API renvoie la même probabilité que le modèle appelé directement |

On ne teste pas que le modèle a « raison » : on ne connaît pas la bonne réponse pour une réservation future. On teste que **l'intégration** est correcte.

⚠️ Pour comparer des nombres décimaux, utilise `pytest.approx` : `assert proba == pytest.approx(0.82, abs=1e-4)`. L'égalité stricte entre flottants échoue souvent pour des raisons d'arrondi.

## Pour aller plus loin

- Tester une application FastAPI : https://fastapi.tiangolo.com/tutorial/testing/
- Paramétrer des tests : https://docs.pytest.org/en/stable/how-to/parametrize.html
