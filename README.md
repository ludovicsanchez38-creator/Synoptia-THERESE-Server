# Thérèse Server

Assistant IA multi-utilisateurs pour collectivités et PME.

## Fonctionnalités

- **Multi-utilisateurs** : authentification JWT, rôles (admin, manager, agent)
- **Multi-organisations** : isolation des données par organisation
- **Multi-modèles** : Claude, Mistral, GPT, Gemini, Ollama (modèles locaux)
- **RAG** : indexation de documents avec Qdrant
- **Dashboard admin** : gestion utilisateurs, usage, coûts, modèles
- **Audit trail** : journalisation de toutes les interactions
- **RGPD** : export/suppression données, rétention configurable
- **On-premise** : déployable sans dépendance cloud

## Stack technique

- **Backend** : Python FastAPI + SQLModel + Alembic
- **Frontend** : React + Vite + TailwindCSS + Zustand
- **Base de données** : PostgreSQL (prod) / SQLite (dev)
- **Vectoriel** : Qdrant
- **Conteneurs** : Docker + docker-compose
- **Reverse proxy** : Caddy

## Démarrage rapide

```bash
# Cloner
git clone https://github.com/ludovicsanchez38-creator/Synoptia-THERESE-Server.git
cd Synoptia-THERESE-Server

# Configuration
cp .env.example .env
# Éditer .env avec vos clés API et secrets

# Lancer
docker compose up -d

# Accéder
open http://localhost
```

## Développement

```bash
# Backend seul (SQLite)
cd backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# Frontend seul
cd frontend
npm install
npm run dev
```

## Architecture

```
therese-server/
├── backend/          # FastAPI (Python)
│   ├── app/
│   │   ├── auth/     # Authentification JWT
│   │   ├── models/   # SQLModel entities
│   │   ├── routers/  # Endpoints API
│   │   └── services/ # Logique métier
│   └── tests/
├── frontend/         # React (TypeScript)
│   └── src/
│       ├── pages/    # Login, Chat, Admin
│       ├── stores/   # Zustand state
│       └── services/ # API clients
├── docker-compose.yml
├── Caddyfile
└── .env.example
```

## Licence

AGPL-3.0 - Voir [LICENSE](LICENSE)

## Auteur

Ludovic Sanchez - [Synoptïa](https://synoptia.fr)
