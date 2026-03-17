# CLAUDE.md - Thérèse Server

## Projet

- **Nom** : Thérèse Server
- **Description** : Assistant IA multi-utilisateurs pour collectivités et PME
- **Version** : 0.1.0
- **Licence** : AGPL-3.0
- **Repo** : github.com/ludovicsanchez38-creator/Synoptia-THERESE-Server
- **Base** : fork adapté du backend Synoptia-THERESE (v0.7.2-alpha desktop)

## Stack

- **Backend** : Python 3.11+, FastAPI, SQLModel, Alembic, asyncpg
- **Frontend** : React 19, Vite, TailwindCSS 4, Zustand 5, TypeScript 5
- **Auth** : FastAPI-Users, JWT
- **DB** : PostgreSQL 16 (prod), SQLite (dev)
- **Vectoriel** : Qdrant
- **Infra** : Docker Compose, Caddy

## Conventions

- Python : UV, type hints, ruff (E/F/W/I/B/C90/SIM)
- TypeScript : strict mode, ESLint
- Commits : en français
- Accents obligatoires (é, è, ê, à, etc.)
- Pas de tiret long (--) -> tiret court (-) ou parenthèses
- Pas de `rm` -> `mv fichier ~/.Trash/`

## Architecture

```
backend/app/
├── auth/          # FastAPI-Users, JWT, RBAC
├── models/        # SQLModel entities + database.py
│   ├── entities.py        # Tables métier (27 existantes + User, Org, AuditLog)
│   └── database.py        # PostgreSQL async + SQLite dev
├── routers/       # 28 routers FastAPI (adaptés multi-user)
├── services/      # Logique métier
│   ├── llm.py             # Multi-provider (Claude, Mistral, GPT, Gemini, Ollama)
│   ├── qdrant.py          # RAG vectoriel
│   ├── providers/         # Adaptateurs LLM
│   └── encryption.py      # Fernet (env-based, pas Keychain)
└── config.py      # Pydantic settings

frontend/src/
├── pages/         # Login, Chat, Admin
├── stores/        # Zustand (auth, chat, admin)
├── services/api/  # HTTP clients
└── components/    # UI components
```

## Multi-tenancy

- Row-level isolation : `user_id` + `org_id` FK sur toutes les tables
- Roles : admin (DSI), manager (chef de service), agent (utilisateur)
- Chaque requête API est scopée par le current_user

## Tests

```bash
# Backend
cd backend && pytest --timeout=30

# Frontend
cd frontend && npm test
```

## Docker

```bash
docker compose up -d          # Tout lancer
docker compose logs -f backend # Logs backend
docker compose down           # Tout arrêter
```
