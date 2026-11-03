# Linux minimal avec Python 3.11 : environ 130 Mo, contre 1 Go pour l'image complète
FROM python:3.11-slim

WORKDIR /app

# Les dépendances d'abord : la couche est réutilisée tant que requirements.txt ne bouge pas.
# --no-compile économise 99 Mo de .pyc, et les dossiers tests de scipy, pandas et
# sklearn en pèsent 101 autres. Le nettoyage est dans le MÊME RUN, sinon la couche
# précédente garde les fichiers et l'image ne maigrit pas.
COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt \
    && find /usr/local/lib/python3.11/site-packages -type d -name tests -prune -exec rm -rf {} +

# Le code et le modèle ensuite, car ils changent à chaque commit
COPY app/ app/
COPY model/ model/

# Informatif : documente le port, ne l'ouvre pas
EXPOSE 8000

# Docker interroge /health : le conteneur passe « healthy » quand le modèle est chargé
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=5     CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# 0.0.0.0 et non 127.0.0.1, sinon l'API n'est joignable que depuis le conteneur
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
