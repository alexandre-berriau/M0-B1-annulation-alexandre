"""Schémas Pydantic : format des entrées et des sorties de l'API."""

from pydantic import BaseModel


class Booking(BaseModel):
    """Une réservation, telle que saisie dans le logiciel de gestion hôtelière.

    Les noms de champs sont ceux du jeu de données d'entraînement :
    le modèle attend exactement ces colonnes.

    TODO (tâche 3) : ces champs ne sont pas contraints. Une valeur absurde
    (type d'hôtel inconnu, nombre d'adultes négatif…) passe la validation
    et arrive jusqu'au modèle. Ajoute les contraintes nécessaires
    (indices : `Literal`, `Field(ge=..., le=...)`).
    """

    hotel: str
    lead_time: int
    arrival_date_month: str
    stays_in_weekend_nights: int
    stays_in_week_nights: int
    adults: int
    children: int
    market_segment: str
    deposit_type: str
    customer_type: str
    country: str
    adr: float
    previous_cancellations: int
    total_of_special_requests: int
    required_car_parking_spaces: int


class PredictionResponse(BaseModel):
    """Réponse de /predict."""

    annulation: bool
    probabilite_annulation: float
