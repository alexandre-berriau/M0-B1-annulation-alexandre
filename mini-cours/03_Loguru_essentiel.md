# 03 — Loguru : l'essentiel pour journaliser une API

## 1. Pourquoi des logs ?

Ton API tourne sur un serveur d'Escale Atlantique. Un matin, le service réservations t'écrit : « les scores d'hier après-midi étaient bizarres ». Sans logs, impossible de savoir quelles requêtes sont arrivées, ce que le modèle a répondu, ni combien de temps ça a pris.

Les logs servent à :

- **déboguer** : retrouver l'entrée qui a provoqué une erreur ;
- **surveiller** : repérer une latence qui augmente, un taux d'erreurs qui grimpe ;
- **auditer** : savoir ce que le modèle a décidé, et quand. Au module 5, on s'en servira pour détecter les dérives du modèle.

Un `print()` ne suffit pas : il n'a ni horodatage, ni niveau de gravité, il disparaît à la fermeture du terminal et ne s'écrit pas dans un fichier.

## 2. Loguru en 3 lignes

Le module `logging` de Python fonctionne, mais sa configuration est verbeuse. **Loguru** offre un logger prêt à l'emploi :

```python
from loguru import logger

logger.info("Modèle chargé")
logger.warning("Requête refusée : champ manquant")
logger.error("Le modèle a planté")
```

```
2026-11-03 10:42:17.351 | INFO     | app.main:lifespan:24 - Modèle chargé
```

### Les niveaux

| Niveau | Quand l'utiliser |
|---|---|
| `DEBUG` | détails utiles seulement pendant le développement |
| `INFO` | le fonctionnement normal : une requête traitée, un modèle chargé |
| `WARNING` | quelque chose d'anormal mais géré : une entrée refusée |
| `ERROR` | une opération a échoué |
| `CRITICAL` | le service ne peut plus fonctionner |

### Insérer des valeurs

Loguru utilise la syntaxe `{}` de `str.format` :

```python
logger.info("Prédiction : {} en {:.1f} ms", resultat, duree_ms)
```

## 3. Écrire dans un fichier : les *sinks*

Un **sink** est une destination des logs. Par défaut, Loguru écrit dans la console. On en ajoute avec `logger.add` :

```python
logger.add(
    "logs/api.log",
    level="INFO",            # on ignore les DEBUG
    rotation="5 MB",         # nouveau fichier quand celui-ci atteint 5 Mo
    retention="7 days",      # on supprime les fichiers de plus de 7 jours
    compression="zip",       # les anciens fichiers sont compressés
    encoding="utf-8",        # accents corrects sous Windows
)
```

Le dossier `logs/` est créé automatiquement. Pense à l'ajouter au `.gitignore` : les logs ne se versionnent pas.

**Rotation et rétention** évitent qu'un fichier de logs grossisse jusqu'à remplir le disque du serveur, ce qui arrive plus vite qu'on ne le croit sur une API très sollicitée.

### Personnaliser le format

```python
FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
logger.add("logs/api.log", format=FORMAT)
```

### Repartir de zéro

`logger.remove()` supprime **tous** les sinks, y compris la console par défaut. C'est utile pour tout configurer au même endroit, et pour éviter d'ajouter deux fois le même fichier si la configuration est appelée plusieurs fois (ce qui arrive avec les tests). Attention à l'ordre : `remove()` d'abord, puis les `add()`.

## 4. Mesurer une durée

```python
import time

start = time.perf_counter()
# ... l'opération à mesurer ...
duree_ms = (time.perf_counter() - start) * 1000
```

`perf_counter` est l'horloge prévue pour mesurer des durées. `time.time()` peut sauter, par exemple lors d'un changement d'heure.

## 5. Que faut-il journaliser… et ne pas journaliser ?

Les logs sont des **données**, conservées sur un serveur, parfois lues par plusieurs personnes. Le RGPD s'y applique.

| ✅ À journaliser | ⚠️ À limiter ou éviter |
|---|---|
| la route appelée, la durée, le résultat | noms, e-mails, téléphones, numéros de chambre |
| les erreurs et leur type | le contenu complet d'un texte libre (un avis client peut contenir n'importe quoi) |
| la version du modèle | mots de passe, clés d'API, jetons |

En M0-B2, tu tronqueras les avis à 80 caractères pour cette raison. Pour M0-B1, pose-toi la question : la réservation contient-elle des données sur une personne ?


## Pour aller plus loin

- Documentation de Loguru : https://loguru.readthedocs.io/
