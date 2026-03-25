# --- Etape 1 : Build ---
FROM node:22-alpine AS build
WORKDIR /app

# Dependances Node - installees avant le code pour profiter du cache Docker
COPY package.json package-lock.json* ./
RUN npm ci

# Copier le code source et construire
COPY . .
RUN npm run build

# --- Etape 2 : Serveur nginx ---
FROM nginx:alpine

# Copier le build React
COPY --from=build /app/dist /usr/share/nginx/html

# Config nginx pour SPA (fallback index.html) + gzip + cache
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --spider -q http://localhost:3000/ || exit 1
