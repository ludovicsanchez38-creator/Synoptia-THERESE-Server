# --- Etape 1 : Build ---
FROM node:22-alpine AS build
WORKDIR /app

# Dependances Node - installees avant le code pour profiter du cache Docker
COPY package.json package-lock.json* ./
RUN npm ci

# Copier le code source et construire
COPY . .
RUN npm run build

# --- Etape 2 : Serveur statique ---
FROM node:22-alpine
WORKDIR /app

RUN npm install -g serve@14

# Copier uniquement le build final (image legere)
COPY --from=build /app/dist ./dist

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --spider -q http://localhost:3000/ || exit 1

CMD ["serve", "-s", "dist", "-l", "3000"]
