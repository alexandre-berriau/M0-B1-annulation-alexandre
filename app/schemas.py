"""Schémas Pydantic : format des entrées et des sorties de l'API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Valeurs relevées dans data/hotel_bookings_sample.csv
Hotel = Literal["City Hotel", "Resort Hotel"]

MoisArrivee = Literal[
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

SegmentMarche = Literal[
    "Aviation",
    "Complementary",
    "Corporate",
    "Direct",
    "Groups",
    "Offline TA/TO",
    "Online TA",
]

TypeAcompte = Literal["No Deposit", "Non Refund", "Refundable"]

TypeClient = Literal["Contract", "Group", "Transient", "Transient-Party"]

# Pré-remplit le bouton « Try it out » de Swagger
EXEMPLE_RESERVATION = {
    "hotel": "Resort Hotel",
    "lead_time": 164,
    "arrival_date_month": "November",
    "stays_in_weekend_nights": 2,
    "stays_in_week_nights": 5,
    "adults": 2,
    "children": 0,
    "market_segment": "Online TA",
    "deposit_type": "No Deposit",
    "customer_type": "Transient",
    "country": "FRA",
    "adr": 61.2,
    "previous_cancellations": 0,
    "total_of_special_requests": 0,
    "required_car_parking_spaces": 1,
}


class Booking(BaseModel):
    """Une réservation, telle que saisie dans le logiciel de gestion hôtelière.

    3.5 — bornes plus larges que l'échantillon : refuser une vraie
    réservation coûte plus cher que laisser passer une valeur rare.
    """

    model_config = ConfigDict(
        extra="forbid",  # un champ inconnu remonte au lieu d'être ignoré
        json_schema_extra={"examples": [EXEMPLE_RESERVATION]},
    )

    hotel: Hotel
    lead_time: int = Field(ge=0, le=800)  # jours avant l'arrivée
    arrival_date_month: MoisArrivee
    stays_in_weekend_nights: int = Field(ge=0, le=30)
    stays_in_week_nights: int = Field(ge=0, le=50)
    adults: int = Field(ge=0, le=10)  # ge=0 : 6 lignes du CSV ont adults=0
    children: int = Field(ge=0, le=10)
    market_segment: SegmentMarche
    deposit_type: TypeAcompte
    customer_type: TypeClient
    country: str = Field(pattern=r"^[A-Z]{2,3}$")  # CN et FRA coexistent
    adr: float = Field(ge=0, le=2000)  # prix moyen par nuit, en euros
    previous_cancellations: int = Field(ge=0, le=100)
    total_of_special_requests: int = Field(ge=0, le=10)
    required_car_parking_spaces: int = Field(ge=0, le=10)


class PredictionResponse(BaseModel):
    """Réponse de /predict."""

    annulation: bool
    probabilite_annulation: float = Field(ge=0.0, le=1.0)
