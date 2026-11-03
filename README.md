# Escale Atlantique — API de prédiction d'annulation

API REST qui estime, pour une réservation donnée, la probabilité qu'elle soit annulée.
Elle expose un modèle scikit-learn livré par l'équipe data d'Escale Atlantique.

Une interface web Angular (`UI/`) permet de saisir une réservation, de lire la
prédiction et de consulter le journal de l'API sans passer par Swagger.

Brief **M0-B1** (FastIA) — FastAPI, Pydantic, Loguru, pytest, Docker, Angular.

## Prérequis

- **Python 3.11** — obligatoire. `scikit-learn 1.6.1` n'a pas de paquet précompilé
  pour Python 3.14 : l'installation tente une compilation C++ et échoue.
- Docker, pour la partie conteneurisée (optionnel).
- Node 20 ou plus, uniquement pour développer l'interface hors Docker (optionnel).

## Démarrage rapide

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate    — macOS/Linux : source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- Santé du service : http://localhost:8000/health
- Documentation interactive : http://localhost:8000/docs — le bouton *Try it out* est pré-rempli

## Avec Docker

Les deux services d'un coup — l'API sur le port 8000, l'interface sur le 8001 :

```bash
docker compose up --build
```

- Interface : http://localhost:8001
- API : http://localhost:8000/docs

L'interface attend que l'API soit `healthy` avant de démarrer (`HEALTHCHECK` sur
`/health`). Les logs sont montés dans `./logs` sur la machine hôte, ils survivent donc
aux conteneurs.

Pour l'API seule :

```bash
docker build -t fastia-annulation:dev .
docker run --rm -p 8000:8000 fastia-annulation:dev
curl http://localhost:8000/health
```

L'image contient 375 Mo de fichiers et pèse 117 Mo compressée. `docker images` peut
afficher 520 Mo : cette colonne additionne les blobs compressés **et** l'arborescence
décompressée, elle compte donc deux fois les mêmes données. Pour la taille réelle :

```bash
docker run --rm --entrypoint sh fastia-annulation:dev -c "du -sm /"
```

## Les routes

### `GET /health`

```json
{"status": "ok", "model_loaded": true}
```

### `POST /predict`

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d @data/exemple_reservation.json
```

```json
{"annulation": false, "probabilite_annulation": 0.000265}
```

`annulation` est le verdict du modèle, `probabilite_annulation` est comprise entre 0 et 1.

Les 15 champs sont tous obligatoires. Une valeur hors des listes ci-dessous, une valeur
négative ou un champ inconnu renvoie **422** sans interrompre le service.

| Champ | Valeurs acceptées |
|---|---|
| `hotel` | `City Hotel`, `Resort Hotel` |
| `arrival_date_month` | les 12 mois en anglais (`January`…`December`) |
| `market_segment` | `Aviation`, `Complementary`, `Corporate`, `Direct`, `Groups`, `Offline TA/TO`, `Online TA` |
| `deposit_type` | `No Deposit`, `Non Refund`, `Refundable` |
| `customer_type` | `Contract`, `Group`, `Transient`, `Transient-Party` |
| `country` | code ISO en majuscules, 2 ou 3 lettres (`FRA`, `PRT`, `CN`) |
| `adr` | 0 à 2000 (prix moyen par nuit, en euros) |
| `lead_time` | 0 à 800 (jours avant l'arrivée) |
| `adults`, `children` | 0 à 10 |
| les autres champs numériques | entiers positifs bornés (voir `app/schemas.py`) |

### `GET /logs`

Les dernières lignes de `logs/api.log`, entre 1 et 500 (50 par défaut). C'est ce que
l'interface web affiche.

```bash
curl "http://localhost:8000/logs?lignes=10"
```

```json
{"lignes": ["2026-11-03 14:33:17.330 | INFO | app.main:predict:107 - /predict …"]}
```

⚠️ Cette route expose le contenu des réservations journalisées. Elle convient à un
usage local ou à un réseau interne, pas à une exposition publique sans contrôle d'accès.

## Interface web

Application Angular 22 dans `UI/`, servie par nginx. Elle appelle l'API sous `/api/`,
que nginx relaie vers le conteneur `api` : le navigateur ne voit qu'une seule origine,
aucune configuration CORS n'est donc nécessaire.

Le plus simple est de la lancer avec `docker compose up` (voir plus haut). Pour la
développer hors Docker, avec l'API lancée en parallèle sur le port 8000 :

```bash
cd UI
npm install
npm start
```

`proxy.conf.json` redirige alors `/api` vers `http://localhost:8000`.

## Tests

```bash
pytest -v
```

28 tests : cas valide, cohérence entre la prédiction et la probabilité, 11 entrées
refusées en 422, la survie du service après un refus, les deux types d'hôtel,
5 réservations réelles tirées du CSV, un test de fidélité qui compare la réponse de
l'API au modèle appelé directement, 4 tests de `/logs` et les 2 tests de `/health`
fournis.

## Journalisation

Chaque appel écrit une ligne dans `logs/api.log` (rotation à 5 Mo, rétention 7 jours,
compression zip). Le dossier n'est pas versionné.

```
INFO    | /predict entree={...} annulation=True proba=0.5519 duree=7.7ms
WARNING | /predict refusé en 422 : adults=-3 (Input should be greater than or equal to 0)
```

Le premier appel après le démarrage prend environ 2,7 s, les suivants environ 7 ms :
le `lifespan` charge le modèle au démarrage, mais les couches de calcul de scikit-learn
ne s'initialisent qu'à la première prédiction.

Avec `docker compose`, `./logs` est monté dans le conteneur : les lignes survivent à
son arrêt et restent lisibles depuis la machine hôte. Le service fixe `TZ=Europe/Paris`,
sinon le conteneur journaliserait en UTC et les horodatages seraient décalés par rapport
à un lancement local dans le même fichier.

## Le modèle

Livré dans `model/cancellation_model.joblib` : un `Pipeline` scikit-learn contenant
**à la fois** la préparation des données (imputation, encodage one-hot) et le
classifieur `HistGradientBoostingClassifier`. Les variables catégorielles n'ont donc
pas à être encodées avant l'appel — le pipeline applique la transformation apprise à
l'entraînement. Il attend un `DataFrame` pandas, car il sélectionne ses colonnes par nom.

Performances annoncées sur le jeu de test : accuracy 0,857 · F1 0,797 · ROC-AUC 0,933
(voir `model/model_info.json`).

Les versions de `requirements.txt` sont figées : `scikit-learn` **doit** rester en
1.6.1, version utilisée pour l'entraînement. Le chemin du modèle est surchargeable par
la variable d'environnement `MODEL_PATH`.

## Structure

```
app/
  main.py          # application FastAPI : lifespan, /health, /predict, logs
  schemas.py       # schémas Pydantic : validation des entrées et des sorties
model/
  cancellation_model.joblib   # modèle livré — ne pas modifier
  model_info.json             # fiche d'identité du modèle
  train_baseline.py           # script d'entraînement, pour information
data/
  hotel_bookings_sample.csv   # extrait du jeu d'entraînement (1 000 réservations)
  exemple_reservation.json    # corps de requête d'exemple
tests/
  conftest.py      # fixtures client et reservation_valide
  test_health.py   # tests de /health
  test_predict.py  # tests de /predict
  test_logs.py     # tests de /logs
UI/                # interface Angular servie par nginx
  src/app/         # composant unique : formulaire, résultat, journal
  nginx.conf       # sert les fichiers statiques et relaie /api vers l'API
  Dockerfile       # build Node puis image nginx
mini-cours/        # supports de formation fournis avec le squelette
Dockerfile
docker-compose.yml # API sur 8000, interface sur 8001
requirements.txt   # dépendances, versions figées
pytest.ini
```

## Données

Extrait de *Hotel Booking Demand* — N. Antonio, A. de Almeida, L. Nunes (2019),
*Data in Brief* 22, 41-49. Licence CC BY 4.0.
