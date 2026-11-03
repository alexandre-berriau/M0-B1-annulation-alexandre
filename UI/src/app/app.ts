import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface Prediction {
  annulation: boolean;
  probabilite_annulation: number;
}

interface Reservation {
  hotel: string;
  lead_time: number;
  arrival_date_month: string;
  stays_in_weekend_nights: number;
  stays_in_week_nights: number;
  adults: number;
  children: number;
  market_segment: string;
  deposit_type: string;
  customer_type: string;
  country: string;
  adr: number;
  previous_cancellations: number;
  total_of_special_requests: number;
  required_car_parking_spaces: number;
}

// Mêmes valeurs que les Literal de app/schemas.py : si l'API en refuse une,
// c'est que les deux listes ont divergé.
const HOTELS = ['City Hotel', 'Resort Hotel'];
const MOIS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const SEGMENTS = [
  'Aviation', 'Complementary', 'Corporate', 'Direct',
  'Groups', 'Offline TA/TO', 'Online TA',
];
const ACOMPTES = ['No Deposit', 'Non Refund', 'Refundable'];
const TYPES_CLIENT = ['Contract', 'Group', 'Transient', 'Transient-Party'];

const EXEMPLE: Reservation = {
  hotel: 'Resort Hotel',
  lead_time: 164,
  arrival_date_month: 'November',
  stays_in_weekend_nights: 2,
  stays_in_week_nights: 5,
  adults: 2,
  children: 0,
  market_segment: 'Online TA',
  deposit_type: 'No Deposit',
  customer_type: 'Transient',
  country: 'FRA',
  adr: 61.2,
  previous_cancellations: 0,
  total_of_special_requests: 0,
  required_car_parking_spaces: 1,
};

@Component({
  selector: 'app-root',
  imports: [FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  private readonly http = inject(HttpClient);

  protected readonly hotels = HOTELS;
  protected readonly mois = MOIS;
  protected readonly segments = SEGMENTS;
  protected readonly acomptes = ACOMPTES;
  protected readonly typesClient = TYPES_CLIENT;

  protected reservation: Reservation = { ...EXEMPLE };
  protected readonly prediction = signal<Prediction | null>(null);
  protected readonly erreur = signal<string | null>(null);
  protected readonly chargement = signal(false);
  protected readonly logs = signal<string[]>([]);

  ngOnInit(): void {
    this.rafraichirLogs();
  }

  protected predire(): void {
    this.chargement.set(true);
    this.erreur.set(null);
    this.http.post<Prediction>('/api/predict', this.reservation).subscribe({
      next: (reponse) => {
        this.prediction.set(reponse);
        this.terminer();
      },
      error: (erreur: HttpErrorResponse) => {
        this.prediction.set(null);
        this.erreur.set(this.messageErreur(erreur));
        this.terminer();
      },
    });
  }

  protected reinitialiser(): void {
    this.reservation = { ...EXEMPLE };
    this.prediction.set(null);
    this.erreur.set(null);
  }

  protected rafraichirLogs(): void {
    this.http
      .get<{ lignes: string[] }>('/api/logs?lignes=40')
      .subscribe({ next: (reponse) => this.logs.set(reponse.lignes.reverse()) });
  }

  protected niveau(ligne: string): string {
    if (ligne.includes('| WARNING')) return 'avertissement';
    if (ligne.includes('| ERROR')) return 'erreur';
    return 'info';
  }

  protected pourcentage(valeur: number): string {
    return (valeur * 100).toFixed(2) + ' %';
  }

  // Un appel refusé est journalisé côté API : on recharge aussi après une erreur
  private terminer(): void {
    this.chargement.set(false);
    this.rafraichirLogs();
  }

  private messageErreur(reponse: HttpErrorResponse): string {
    if (reponse.status === 0) {
      return "L'API ne répond pas. Est-elle lancée sur le port 8000 ?";
    }
    const detail = reponse.error?.detail;
    if (Array.isArray(detail)) {
      // 422 : FastAPI renvoie un objet par champ refusé
      return detail
        .map((item: { loc?: string[]; msg?: string }) => `${item.loc?.at(-1)} : ${item.msg}`)
        .join(' · ');
    }
    return `${reponse.status} ${reponse.statusText ?? 'erreur'}`;
  }
}
