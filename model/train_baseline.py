"""Entraînement du modèle de référence — livré par l'équipe data d'Escale Atlantique.

⚠️ Tu n'as PAS à lancer ce script : le modèle entraîné t'est livré dans
`model/cancellation_model.joblib`. Il est fourni pour que tu comprennes
comment le modèle a été construit (colonnes utilisées, préparation des données).

Données : « Hotel Booking Demand » (Antonio, Almeida & Nunes, 2019, Data in Brief,
licence CC BY 4.0) — réservations de 2015 à 2017 dans un hôtel urbain et un resort.

Usage (depuis la racine du repo) :
    python model/train_baseline.py --data chemin/vers/hotel_bookings.csv
"""

import argparse
import json
from datetime import date
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

MODEL_DIR = Path(__file__).resolve().parent

CATEGORICAL_FEATURES = [
    "hotel",
    "arrival_date_month",
    "market_segment",
    "deposit_type",
    "customer_type",
    "country",
]
NUMERICAL_FEATURES = [
    "lead_time",
    "stays_in_weekend_nights",
    "stays_in_week_nights",
    "adults",
    "children",
    "adr",
    "previous_cancellations",
    "total_of_special_requests",
    "required_car_parking_spaces",
]
FEATURES = CATEGORICAL_FEATURES + NUMERICAL_FEATURES
TARGET = "is_canceled"

# Colonnes volontairement écartées : elles « trahissent » la réponse (fuite de données).
# - reservation_status : vaut "Canceled" quand la réservation est annulée
# - booking_changes, assigned_room_type : ne sont connues qu'après la réservation


def build_pipeline() -> Pipeline:
    preprocessing = ColumnTransformer(
        transformers=[
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="constant", fill_value="Unknown")),
                        (
                            "encode",
                            OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=50),
                        ),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
            ("num", SimpleImputer(strategy="median"), NUMERICAL_FEATURES),
        ],
        sparse_threshold=0,
    )
    return Pipeline(
        [
            ("preprocessing", preprocessing),
            ("classifier", HistGradientBoostingClassifier(max_iter=200, random_state=42)),
        ]
    )


def main(data_path: Path) -> None:
    df = pd.read_csv(data_path)
    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    model = build_pipeline()
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    pred = model.predict(X_test)
    metrics = {
        "accuracy": round(accuracy_score(y_test, pred), 3),
        "f1": round(f1_score(y_test, pred), 3),
        "roc_auc": round(float(roc_auc_score(y_test, proba)), 3),
    }
    print("Métriques sur le jeu de test :", metrics)

    joblib.dump(model, MODEL_DIR / "cancellation_model.joblib")
    info = {
        "model_name": "cancellation_model",
        "version": "1.0.0",
        "trained_on": date.today().isoformat(),
        "algorithm": "HistGradientBoostingClassifier",
        "scikit_learn_version": sklearn.__version__,
        "features": FEATURES,
        "target": TARGET,
        "n_train": len(X_train),
        "test_metrics": metrics,
    }
    (MODEL_DIR / "model_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print("Modèle sauvegardé dans", MODEL_DIR)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True, help="CSV complet hotel_bookings")
    main(parser.parse_args().data)
