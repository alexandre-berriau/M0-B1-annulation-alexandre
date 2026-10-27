# 01 — FastAPI : l'essentiel pour exposer un modèle


## 1. Pourquoi une API ?

Un modèle dans un notebook ne sert qu'à toi. Pour que le logiciel de gestion hôtelière d'Escale Atlantique l'utilise, il faut qu'il puisse lui **envoyer une réservation et recevoir une réponse**, sans connaître Python ni scikit-learn.

Une **API REST** est ce contrat :

```
Client (n'importe quel langage)           Ton API
        │  POST /predict                      │
        │  {"hotel": "City Hotel", ...}  ───▶ │  valide l'entrée
        │                                     │  appelle le modèle
        │  ◀───  {"annulation": true, ...}    │  renvoie du JSON
```

- **Route** (*endpoint*) : une adresse, par exemple `/predict`.
- **Méthode HTTP** : `GET` pour lire (`/health`), `POST` pour envoyer des données à traiter (`/predict`).
- **JSON** : le format d'échange, en entrée comme en sortie.
- **Code de statut** : `200` tout va bien, `422` entrée invalide, `500` erreur côté serveur, `501` pas encore implémenté.

**FastAPI** est un framework Python qui rend ça très court, valide les entrées automatiquement (avec Pydantic) et génère une documentation interactive.

## 2. Une API minimale

```python
from fastapi import FastAPI

app = FastAPI(title="Mon API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

Lancement, depuis la racine du projet :

```bash
uvicorn app.main:app --reload
```

- `app.main` : le fichier `app/main.py` ;
- `:app` : la variable `app` dans ce fichier ;
- `--reload` : redémarre à chaque modification du code (pour le développement uniquement).

Ouvre ensuite **http://localhost:8000/docs** : c'est **Swagger**, une page générée automatiquement où tu peux tester chaque route avec le bouton *Try it out*. Ce sera ton meilleur outil de débogage.

## 3. Valider les entrées avec Pydantic

On décrit la forme attendue des données avec une classe qui hérite de `BaseModel` :

```python
from pydantic import BaseModel


class Chambre(BaseModel):
    type_chambre: str
    nb_personnes: int
    prix_nuit: float
```

Puis on l'utilise comme paramètre d'une route `POST` :

```python
@app.post("/estimer")
def estimer(chambre: Chambre) -> dict:
    return {"prix_total": chambre.prix_nuit * 3}
```

FastAPI lit le JSON reçu, le **convertit** en objet `Chambre`, et **refuse automatiquement** (code 422) ce qui ne correspond pas : champ manquant, `"deux"` au lieu de `2`…

### Aller plus loin que le type

Vérifier le type ne suffit pas : `nb_personnes = -3` est un entier valide… et une absurdité. Deux outils :

```python
from typing import Literal

from pydantic import BaseModel, Field


class Chambre(BaseModel):
    # Seules ces valeurs sont acceptées
    type_chambre: Literal["simple", "double", "suite"]
    # Bornes numériques : ge = « supérieur ou égal », le = « inférieur ou égal »
    nb_personnes: int = Field(ge=1, le=6)
    prix_nuit: float = Field(gt=0, description="Prix en euros")
```

| Besoin | Outil |
|---|---|
| Liste fermée de valeurs | `Literal["a", "b", "c"]` |
| Bornes numériques | `Field(ge=..., le=...)`, `Field(gt=0)` |
| Longueur d'un texte | `Field(min_length=1, max_length=2000)` |
| Format d'un texte | `Field(pattern=r"^[A-Z]{3}$")` |
| Refuser les champs inconnus | `model_config = ConfigDict(extra="forbid")` |

### Décrire la réponse

On peut aussi déclarer le format de **sortie** : FastAPI vérifie alors ce que tu renvoies et le documente dans Swagger.

```python
class Estimation(BaseModel):
    prix_total: float


@app.post("/estimer", response_model=Estimation)
def estimer(chambre: Chambre) -> Estimation:
    return Estimation(prix_total=chambre.prix_nuit * 3)
```

## 4. Charger le modèle une seule fois : le `lifespan`

Charger un modèle prend du temps (quelques centaines de millisecondes pour un `.joblib`, plusieurs secondes pour un modèle de NLP). Le recharger **à chaque requête** serait catastrophique.

Le `lifespan` est une fonction exécutée **au démarrage** du serveur (avant le `yield`) et **à son arrêt** (après) :

```python
from contextlib import asynccontextmanager

import joblib
from fastapi import FastAPI

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["model"] = joblib.load("model/mon_modele.joblib")  # au démarrage
    yield                                                    # le serveur tourne
    state.clear()                                            # à l'arrêt


app = FastAPI(lifespan=lifespan)
```

Dans les routes, on récupère le modèle avec `state["model"]`.

## 5. Appeler un modèle scikit-learn depuis une route

Un modèle scikit-learn attend un **tableau de lignes**, pas un objet seul. Et un `Pipeline` qui contient sa propre préparation des données (encodage, imputation) attend les **mêmes noms de colonnes** qu'à l'entraînement : il faut donc un `DataFrame` pandas.

```python
import pandas as pd

ligne = pd.DataFrame([chambre.model_dump()])   # 1 objet → dict → DataFrame d'1 ligne
#                     ^ liste d'un seul dict : 1 ligne, une colonne par champ

prediction = model.predict(ligne)              # array([1])
probas = model.predict_proba(ligne)            # array([[0.18, 0.82]])
```

Deux détails importants :

- **Tout est un tableau** : `predict` renvoie `array([1])`, il faut prendre `[0]`. `predict_proba` renvoie une ligne par entrée et **une colonne par classe** : `model.classes_` indique l'ordre des colonnes.
- **numpy n'est pas du JSON** : un `numpy.int64` ou un `numpy.bool_` ne passe pas dans la réponse. Convertis avec `int(...)`, `float(...)` ou `bool(...)`.


## Pour aller plus loin

- Documentation officielle (tutoriel très bien fait, en anglais) : https://fastapi.tiangolo.com/tutorial/
- Validation Pydantic : https://docs.pydantic.dev/latest/concepts/fields/
