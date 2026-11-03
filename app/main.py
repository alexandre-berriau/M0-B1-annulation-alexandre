"""API de prédiction d'annulation — Escale Atlantique (mission FastIA)."""

import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from loguru import logger

from app.schemas import Booking, PredictionResponse

ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = Path(os.getenv("MODEL_PATH", ROOT_DIR / "model" / "cancellation_model.joblib"))

# Journalisation : remove() d'abord, sinon le sink console par défaut double les lignes
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(
    ROOT_DIR / "logs" / "api.log",
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
