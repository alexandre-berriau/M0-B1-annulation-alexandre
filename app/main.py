"""API de prédiction d'annulation — Escale Atlantique (mission FastIA)."""

import json
import os
import sys
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from loguru import logger

from app.schemas import (
    BatchRequest,
    BatchResponse,
    Booking,
    InfoResponse,
    LogsResponse,
    PredictionResponse,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = Path(os.getenv("MODEL_PATH", ROOT_DIR / "model" / "cancellation_model.joblib"))
INFO_PATH = MODEL_PATH.parent / "model_info.json"
LOG_PATH = ROOT_DIR / "logs" / "api.log"

# Journalisation : remove() d'abord, sinon le sink console par défaut double les lignes
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(
    LOG_PATH,
    level="INFO",
    rotation="5 MB",  # nouveau fichier au-delà de 5 Mo
    retention="7 days",  # les plus vieux sont supprimés
    compression="zip",  # les archives sont compressées
    encoding="utf-8",  # accents corrects sous Windows
)

# Objets partagés par toutes les requêtes (ici : le modèle)
state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Exécuté UNE fois au démarrage : on charge le modèle en mémoire
    state["model"] = joblib.load(MODEL_PATH)
    state["info"] = json.loads(INFO_PATH.read_text(encoding="utf-8"))
    logger.info("Modèle chargé depuis {}", MODEL_PATH)
    yield
    # Exécuté à l'arrêt du serveur
    state.clear()
    logger.info("Modèle déchargé, arrêt du service")


app = FastAPI(
    title="Escale Atlantique — Prédiction d'annulation",
    description="Estime la probabilité qu'une réservation soit annulée.",
    version="0.1.0",
    lifespan=lifespan,
)


def motif_refus(erreur: dict) -> str:
    """Un champ refusé en une ligne. Sur un champ manquant, Pydantic met tout
    le corps de la requête dans `input` : on ne le recopie pas."""
    if erreur["type"] == "missing":
        return f"{erreur['loc'][-1]} (manquant)"
    return f"{erreur['loc'][-1]}={erreur.get('input')!r} ({erreur['msg']})"


@app.exception_handler(RequestValidationError)
async def journalise_422(request: Request, exc: RequestValidationError):
    """Journalise les entrées refusées, que /predict ne voit jamais."""
    motifs = [motif_refus(e) for e in exc.errors()]
    logger.warning("{} refusé en 422 : {}", request.url.path, " ; ".join(motifs))
    # Délégué au handler natif : le corps de la réponse reste inchangé
    return await request_validation_exception_handler(request, exc)


@app.get("/health")
def health() -> dict:
    """Le service est-il en vie, et le modèle chargé ?"""
    return {"status": "ok", "model_loaded": "model" in state}


@app.post("/predict", response_model=PredictionResponse)
def predict(booking: Booking) -> PredictionResponse:
    """Prédit l'annulation d'une réservation. Entrée déjà validée par Pydantic."""
    debut = time.perf_counter()  # perf_counter et non time(), qui peut sauter

    # 3.1 — le modèle que le lifespan a chargé au démarrage
    model = state.get("model")
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    # 3.2 — DataFrame d'une ligne : le pipeline sélectionne ses colonnes par nom
    ligne = pd.DataFrame([booking.model_dump()])[list(model.feature_names_in_)]

    # 3.3 — colonne 1 de predict_proba, car model.classes_ vaut [0, 1]
    annulation = model.predict(ligne)[0]
    probabilite = model.predict_proba(ligne)[0, 1]

    # 3.4 — bool() et float() : numpy ne se sérialise pas en JSON
    reponse = PredictionResponse(
        annulation=bool(annulation),
        probabilite_annulation=float(probabilite),
    )

    # 4 — une ligne par appel : entrée, prédiction, durée. Pas d'identifiant
    # direct dans une réservation (ni nom, ni e-mail), donc rien à tronquer.
    duree_ms = (time.perf_counter() - debut) * 1000
    logger.info(
        "/predict entree={} annulation={} proba={:.4f} duree={:.1f}ms",
        booking.model_dump(),
        reponse.annulation,
        reponse.probabilite_annulation,
        duree_ms,
    )
    return reponse


@app.post("/predict/batch", response_model=BatchResponse)
def predict_batch(requete: BatchRequest) -> BatchResponse:
    """Prédit une liste de réservations en un seul passage dans le modèle."""
    debut = time.perf_counter()

    model = state.get("model")
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    # Un seul DataFrame pour toutes les réservations : le modèle est vectorisé,
    # 500 lignes d'un coup coûtent bien moins que 500 appels séparés.
    lignes = pd.DataFrame([reservation.model_dump() for reservation in requete.reservations])
    lignes = lignes[list(model.feature_names_in_)]

    annulations = model.predict(lignes)
    probabilites = model.predict_proba(lignes)[:, 1]
    predictions = [
        PredictionResponse(annulation=bool(annulation), probabilite_annulation=float(probabilite))
        for annulation, probabilite in zip(annulations, probabilites)
    ]

    duree_ms = (time.perf_counter() - debut) * 1000
    logger.info(
        "/predict/batch {}/{} annulations prédites, duree={:.1f}ms",
        sum(p.annulation for p in predictions),
        len(predictions),
        duree_ms,
    )
    return BatchResponse(predictions=predictions)


@app.get("/info", response_model=InfoResponse)
def info() -> InfoResponse:
    """Nom, version et colonnes attendues du modèle chargé."""
    fiche = state.get("info")
    if fiche is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")
    # Les colonnes viennent du modèle lui-même, pas du JSON : si les deux
    # divergeaient, c'est le modèle qui fait foi.
    return InfoResponse(**{**fiche, "features": list(state["model"].feature_names_in_)})


@app.get("/logs", response_model=LogsResponse)
def logs(lignes: int = Query(50, ge=1, le=500)) -> LogsResponse:
    """Les dernières lignes de logs/api.log, affichées par l'interface web."""
    if not LOG_PATH.exists():
        return LogsResponse(lignes=[])
    with LOG_PATH.open(encoding="utf-8") as fichier:
        # deque(maxlen=...) ne garde que la fin : inutile de charger tout le fichier
        dernieres = deque(fichier, maxlen=lignes)
    return LogsResponse(lignes=[ligne.rstrip() for ligne in dernieres])
