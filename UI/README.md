# Interface web — Escale Atlantique

Application Angular 22 qui permet de saisir une réservation, de lire la prédiction
renvoyée par l'API et de consulter son journal.

Elle appelle l'API sous `/api/` : nginx relaie vers le conteneur `api` en production,
`proxy.conf.json` vers `http://localhost:8000` en développement.

```bash
npm install
npm start     # http://localhost:4200, l'API doit tourner sur le port 8000
npm run build # sortie dans dist/annulation-ui/browser
```

Le plus simple reste `docker compose up` depuis la racine du dépôt : l'interface est
alors servie sur http://localhost:8001. Voir le [README principal](../README.md).
