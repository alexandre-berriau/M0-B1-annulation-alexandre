# 02 — Docker : l'essentiel pour conteneuriser une API


## 1. Le problème que Docker résout

« Ça marche sur ma machine. » Ton API dépend de Python 3.11, de scikit-learn **exactement** en 1.6.1 (sinon le `.joblib` ne se charge pas), de pandas, de FastAPI… L'équipe technique d'Escale Atlantique a peut-être Python 3.9, ou pas de Python du tout.

Docker emballe **l'application et tout ce dont elle a besoin** (système, Python, bibliothèques, modèle) dans une boîte qui tourne à l'identique partout.

| Notion | Analogie | En pratique |
|---|---|---|
| **Dockerfile** | la recette | un fichier texte qui décrit comment construire l'image |
| **Image** | le plat surgelé | le résultat de la construction, figé, partageable |
| **Conteneur** | le plat réchauffé | une image en cours d'exécution ; on peut en lancer plusieurs |

## 2. Un Dockerfile, instruction par instruction

```dockerfile
# Image de départ : un Linux minimal avec Python 3.11 déjà installé
FROM python:3.11-slim

# Dossier de travail dans le conteneur (créé s'il n'existe pas)
WORKDIR /app

# Copier un fichier de ta machine vers l'image
COPY requirements.txt .

# Exécuter une commande PENDANT la construction de l'image
RUN pip install --no-cache-dir -r requirements.txt

COPY mon_code/ mon_code/

# Documenter le port utilisé (ne l'ouvre pas, c'est informatif)
EXPOSE 8000

# La commande lancée au DÉMARRAGE du conteneur
CMD ["python", "-m", "mon_code"]
```

| Instruction | Quand s'exécute-t-elle ? |
|---|---|
| `RUN` | une fois, à la **construction** de l'image (`docker build`) |
| `CMD` | à chaque **démarrage** d'un conteneur (`docker run`) |

### L'ordre compte : le cache

Docker construit l'image **couche par couche** et réutilise les couches qui n'ont pas changé. Si tu copies tout ton code **avant** d'installer les dépendances, la moindre modification d'un fichier Python relance un `pip install` de plusieurs minutes.

La bonne pratique : **d'abord** `requirements.txt` et l'installation (change rarement), **ensuite** le code (change souvent).

### Garder une image légère

- Partir d'une image `-slim` (environ 130 Mo) plutôt que de l'image complète (environ 1 Go).
- `pip install --no-cache-dir` : ne pas garder les archives téléchargées dans l'image.
- Ne copier **que ce qui sert à faire tourner le service**, et utiliser un fichier `.dockerignore` (même syntaxe que `.gitignore`) pour exclure le reste : environnement virtuel, `__pycache__`, logs, données d'entraînement, `.git`…

## 3. Le réseau : `0.0.0.0` et `-p`

Deux pièges réseau expliquent la majorité des « ça ne répond pas » :

**Dans le conteneur**, uvicorn doit écouter sur `0.0.0.0` (toutes les interfaces). Par défaut, il écoute sur `127.0.0.1`, c'est-à-dire **uniquement depuis l'intérieur du conteneur** : ta machine ne peut pas le joindre.

**Entre ta machine et le conteneur**, il faut publier le port avec `-p port_hôte:port_conteneur` :

```
Ta machine                     Conteneur
localhost:8000  ──── -p 8000:8000 ───▶  0.0.0.0:8000 (uvicorn)
```

## 4. Les commandes du quotidien

```bash
docker build -t mon-api:dev .              # construire l'image (le "." = dossier contenant le Dockerfile)
docker images                              # lister les images et leur taille
docker run --rm -p 8000:8000 mon-api:dev   # lancer un conteneur (--rm : supprimé à l'arrêt)
docker ps                                  # lister les conteneurs en cours
docker logs <id_ou_nom>                    # voir ce que le conteneur affiche
docker exec -it <id_ou_nom> bash           # ouvrir un terminal DANS le conteneur
docker stop <id_ou_nom>                    # arrêter un conteneur
```

Le `-t mon-api:dev` donne un nom (`mon-api`) et une étiquette (`dev`) à l'image.


## Pour aller plus loin

- Référence du Dockerfile : https://docs.docker.com/reference/dockerfile/
- Bonnes pratiques de construction : https://docs.docker.com/build/building/best-practices/
