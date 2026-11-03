import { KeyValuePipe } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

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

interface Info {
  model_name: string;
  version: string;
  trained_on: string;
  algorithm: string;
  scikit_learn_version: string;
  features: string[];
  test_metrics: Record<string, number>;
}

interface Resume {
  total: number;
  annulations: number;
  probabiliteMoyenne: number;
  plusRisquees: { reservation: Reservation; prediction: Prediction }[];
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

const CHAMPS_TEXTE = [
  'hotel', 'arrival_date_month', 'market_segment',
  'deposit_type', 'customer_type', 'country',
];
const CHAMPS_ENTIERS = [
  'lead_time', 'stays_in_weekend_nights', 'stays_in_week_nights', 'adults',
  'children', 'previous_cancellations', 'total_of_special_requests',
  'required_car_parking_spaces',
];
const CHAMPS_NOMBRES = [...CHAMPS_ENTIERS, 'adr'];

// Borne de /predict/batch : au-delà, l'API refuse le lot en 422
const TAILLE_LOT = 500;

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

/**
 * Extrait les 15 colonnes du modèle d'un CSV d'export hôtelier.
 * Le fichier livré en compte 32 et n'a aucun guillemet : un split(',') suffit.
 * Une ligne dont une valeur manque est écartée, sinon elle ferait refuser tout
 * le lot en 422.
 */
function analyserCsv(texte: string): { reservations: Reservation[]; ignorees: number } {
  const lignes = texte.trim().split(/\r?\n/);
  if (lignes.length < 2) {
    throw new Error('Le fichier ne contient aucune ligne de données.');
  }

  const entete = lignes[0].split(',').map((colonne) => colonne.trim());
  const position = new Map(entete.map((colonne, index) => [colonne, index]));
  const absentes = [...CHAMPS_TEXTE, ...CHAMPS_NOMBRES].filter((champ) => !position.has(champ));
  if (absentes.length) {
    throw new Error(`Colonnes absentes du fichier : ${absentes.join(', ')}`);
  }

  const reservations: Reservation[] = [];
  let ignorees = 0;

  for (const ligne of lignes.slice(1)) {
    const cellules = ligne.split(',');
    const brute: Record<string, string | number> = {};
    let complete = true;

    for (const champ of CHAMPS_TEXTE) {
      const valeur = (cellules[position.get(champ)!] ?? '').trim();
      if (!valeur) {
        complete = false;
        break;
      }
      brute[champ] = valeur;
    }

    if (complete) {
      for (const champ of CHAMPS_NOMBRES) {
        const cellule = (cellules[position.get(champ)!] ?? '').trim();
        const valeur = Number(cellule);
        if (cellule === '' || !Number.isFinite(valeur)) {
          complete = false;
          break;
        }
        // Le CSV écrit les entiers en flottant : children vaut « 0.0 »
        brute[champ] = CHAMPS_ENTIERS.includes(champ) ? Math.round(valeur) : valeur;
      }
    }

    if (complete) {
      reservations.push(brute as unknown as Reservation);
    } else {
      ignorees++;
    }
  }

  return { reservations, ignorees };
}

@Component({
  selector: 'app-root',
  imports: [FormsModule, KeyValuePipe],
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

  protected readonly onglet = signal<'saisie' | 'fichier'>('saisie');
  protected readonly info = signal<Info | null>(null);
  protected readonly logs = signal<string[]>([]);

  // Onglet « une réservation »
  protected reservation: Reservation = { ...EXEMPLE };
  protected readonly prediction = signal<Prediction | null>(null);
  protected readonly erreur = signal<string | null>(null);
  protected readonly chargement = signal(false);

  // Onglet « un fichier CSV »
  protected readonly fichierNom = signal<string | null>(null);
  protected readonly lotEnCours = signal(false);
  protected readonly progression = signal(0);
  protected readonly ignorees = signal(0);
  protected readonly resume = signal<Resume | null>(null);
  protected readonly lotErreur = signal<string | null>(null);

  ngOnInit(): void {
    this.http.get<Info>('/api/info').subscribe({ next: (reponse) => this.info.set(reponse) });
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
      error: (reponse: HttpErrorResponse) => {
        this.prediction.set(null);
        this.erreur.set(this.messageErreur(reponse));
        this.terminer();
      },
    });
  }

  protected reinitialiser(): void {
    this.reservation = { ...EXEMPLE };
    this.prediction.set(null);
    this.erreur.set(null);
  }

  protected async importer(evenement: Event): Promise<void> {
    const champ = evenement.target as HTMLInputElement;
    const fichier = champ.files?.[0];
    if (!fichier) {
      return;
    }

    this.fichierNom.set(fichier.name);
    this.lotErreur.set(null);
    this.resume.set(null);
    this.progression.set(0);
    this.lotEnCours.set(true);

    try {
      const { reservations, ignorees } = analyserCsv(await fichier.text());
      this.ignorees.set(ignorees);
      if (!reservations.length) {
        throw new Error('Aucune ligne exploitable : toutes ont au moins une valeur manquante.');
      }
      const predictions = await this.envoyerParLots(reservations);
      this.resume.set(this.resumer(reservations, predictions));
    } catch (erreur) {
      this.lotErreur.set(
        erreur instanceof HttpErrorResponse
          ? this.messageErreur(erreur)
          : (erreur as Error).message,
      );
    } finally {
      this.lotEnCours.set(false);
      this.rafraichirLogs();
      champ.value = ''; // permet de réimporter le même fichier
    }
  }

  protected rafraichirLogs(): void {
    this.http
      .get<{ lignes: string[] }>('/api/logs?lignes=40')
      .subscribe({ next: (reponse) => this.logs.set(reponse.lignes.reverse()) });
  }

  protected niveau(ligne: string): string {
    if (ligne.includes('| WARNING')) {
      return 'avertissement';
    }
    if (ligne.includes('| ERROR')) {
      return 'erreur';
    }
    return 'info';
  }

  protected pourcentage(valeur: number): string {
    return (valeur * 100).toFixed(2) + ' %';
  }

  // Découpe en lots de 500 : un fichier de 1 000 lignes partirait sinon en 422
  private async envoyerParLots(reservations: Reservation[]): Promise<Prediction[]> {
    const predictions: Prediction[] = [];
    for (let debut = 0; debut < reservations.length; debut += TAILLE_LOT) {
      const lot = reservations.slice(debut, debut + TAILLE_LOT);
      const reponse = await firstValueFrom(
        this.http.post<{ predictions: Prediction[] }>('/api/predict/batch', { reservations: lot }),
      );
      predictions.push(...reponse.predictions);
      this.progression.set(predictions.length);
    }
    return predictions;
  }

  private resumer(reservations: Reservation[], predictions: Prediction[]): Resume {
    const total = predictions.length;
    const somme = predictions.reduce((cumul, p) => cumul + p.probabilite_annulation, 0);
    const plusRisquees = reservations
      .map((reservation, index) => ({ reservation, prediction: predictions[index] }))
      .sort((a, b) => b.prediction.probabilite_annulation - a.prediction.probabilite_annulation)
      .slice(0, 10);

    return {
      total,
      annulations: predictions.filter((prediction) => prediction.annulation).length,
      probabiliteMoyenne: total ? somme / total : 0,
      plusRisquees,
    };
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
