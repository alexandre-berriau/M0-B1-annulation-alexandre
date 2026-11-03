# Étape 1 : compiler l'application Angular
FROM node:24-alpine AS build

WORKDIR /ui

# package*.json d'abord : la couche npm ci est réutilisée tant qu'ils ne bougent pas
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npx ng build

# Étape 2 : l'image livrée ne contient que les fichiers statiques et nginx,
# pas Node ni les 500 Mo de node_modules
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /ui/dist/annulation-ui/browser /usr/share/nginx/html

EXPOSE 8001
