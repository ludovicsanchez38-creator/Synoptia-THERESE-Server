# Thérèse Server

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg?logo=docker&logoColor=white)](docker-compose.yml)

**Assistant IA souverain pour collectivités et PME françaises.**

Thérèse Server est la version serveur de [Thérèse](https://github.com/ludovicsanchez38-creator/Synoptia-THERESE), conçue pour être déployée on-premise dans les mairies (300-500 agents) et PME. Zéro dépendance cloud, données souveraines, conformité RGPD intégrée.

### Pourquoi Thérèse ?

- **Souveraineté** : vos données restent chez vous, aucun appel cloud obligatoire (Ollama en local)
- **RGPD natif** : export, anonymisation, consentement, audit trail, ce n'est pas un ajout cosmétique
- **Multi-tenant** : isolation par organisation et par utilisateur, rôles DSI/manager/agent
- **Secteur public** : 10 templates métier (délibérations, courriers, notes de synthèse, RH)
- **Multi-LLM** : Claude, GPT, Gemini, Mistral, ou Ollama 100% local

---

## Fonctionnalités

### Coeur

| Module | Description | Endpoints |
|--------|-------------|-----------|
| **Chat IA** | Conversations multi-modèles avec streaming SSE | 5 |
| **Auth JWT** | Authentification, rôles (admin/manager/agent), RBAC | 9 |
| **Multi-tenant** | Isolation des données par organisation et utilisateur | - |
| **Charte IA** | Acceptation obligatoire avant première utilisation | 1 |
| **Templates** | 10 modèles de prompts secteur public (courrier, délibération, note, synthèse, communication, RH) | 5 |

### Productivité

| Module | Description | Endpoints |
|--------|-------------|-----------|
| **Tâches** | Gestion de tâches avec priorités et filtres (todo/en cours/terminé) | 4 |
| **CRM** | Pipeline commercial, contacts, activités, livrables, import/export | 22 |
| **Commandes** | Commandes utilisateur personnalisées (v1 + v3 avec schéma JSON) | 8 |
| **Calculateurs** | ROI, ICE, RICE, NPV, break-even | 6 |

### Administration

| Module | Description | Endpoints |
|--------|-------------|-----------|
| **Dashboard admin** | KPI, gestion utilisateurs, journal d'audit | 5 |
| **RGPD** | Export/anonymisation données, consentement, stats conformité | 8 |
| **Data** | Backup/restore, export conversations, import données | 12 |
| **Performance** | Métriques streaming, mémoire, indexation, power management | 10 |
| **Personnalisation** | Templates perso, comportement LLM, visibilité features | 5 |

### IA et Recherche

| Module | Description | Endpoints |
|--------|-------------|-----------|
| **RAG** | Upload et indexation documents avec Qdrant (recherche sémantique) | 5 |
| **Memory** | Contacts et projets en mémoire sémantique | 5 |
| **Multi-LLM** | Claude, GPT (OpenAI), Gemini, Mistral, Ollama (local) | - |

> **107 endpoints API** documentés via Swagger UI (`/docs`)

### Rôles et permissions

| Rôle | Chat | Tâches | CRM | Templates | Admin | RGPD |
|------|:----:|:------:|:---:|:---------:|:-----:|:----:|
| **admin** (DSI) | oui | oui | oui | oui | oui | oui |
| **manager** (Chef de service) | oui | oui | oui | oui | non | non |
| **agent** (Utilisateur) | oui | oui | lecture | oui | non | non |

---

## Stack technique

```
Backend   : Python 3.12+ / FastAPI / SQLModel / Alembic / asyncpg
Frontend  : React 19 / TypeScript / Vite 6 / TailwindCSS 4 / Zustand 5
Base      : PostgreSQL 16 (prod) / SQLite (dev)
Vectoriel : Qdrant 1.12
Infra     : Docker Compose / Caddy reverse proxy
LLM       : Anthropic / OpenAI / Google Gemini / Mistral / Ollama
```

---

## Démarrage rapide

### Prérequis

- Docker + Docker Compose
- Une clé API LLM (Anthropic, OpenAI, Google, ou Ollama local)

### Installation

```bash
# Cloner
git clone https://github.com/ludovicsanchez38-creator/Synoptia-THERESE-Server.git
cd Synoptia-THERESE-Server

# Configurer
cp .env.example .env
# Éditer .env : secrets, clés API, domaine

# Lancer
docker compose up -d

# Premier admin créé automatiquement :
#   Email : admin@therese.local
#   Mot de passe : voir les logs (docker compose logs backend)
#   À changer immédiatement
```

L'application est accessible sur `http://localhost` (Caddy gère le HTTPS en production).

### Sans Docker (développement)

```bash
# Backend
cd backend
uv venv && source .venv/bin/activate
uv pip install -e .
uvicorn app.main:app --reload --port 8000

# Frontend (dans un autre terminal)
cd frontend
npm install
npm run dev
```

---

## Architecture

```
therese-server/
|-- backend/
|   |-- app/
|   |   |-- auth/           # JWT, bcrypt, RBAC, seed admin
|   |   |-- models/         # SQLModel (entities, schemas, database)
|   |   |-- routers/        # 19 routers API (chat, crm, tasks, admin, rgpd...)
|   |   |-- services/       # LLM, Qdrant, email, calendar, CRM, audit...
|   |   |-- core/           # Configuration, deps
|   |   +-- main.py         # FastAPI app factory
|   |-- tests/
|   +-- Dockerfile
|-- frontend/
|   |-- src/
|   |   |-- pages/          # Login, Chat, Tasks, CRM, Admin
|   |   |-- components/     # NavBar, CharterModal, chat/*, ui/*
|   |   |-- stores/         # Zustand (auth, chat)
|   |   +-- services/api/   # Clients API typées
|   +-- Dockerfile
|-- docker-compose.yml      # PostgreSQL + Qdrant + Backend + Frontend + Caddy
|-- Caddyfile               # Reverse proxy
|-- .env.example            # Configuration
+-- LICENSE                 # AGPL-3.0
```

### Flux d'authentification

```
Navigateur                    Backend                    PostgreSQL
    |                            |                          |
    |-- POST /api/auth/login --> |                          |
    |                            |-- verify bcrypt -------> |
    |                            |<- user + org ----------- |
    |<-- JWT access + refresh -- |                          |
    |                            |-- log audit -----------> |
    |                            |                          |
    |-- GET /api/auth/me ------> |                          |
    |   (Authorization: Bearer)  |-- decode JWT             |
    |<-- user profile ---------- |-- check role             |
    |                            |-- scope by org_id        |
```

### Multi-tenant

Chaque requête est scopée automatiquement :
- **Conversations** : visibles uniquement par leur créateur (`user_id`)
- **Contacts/CRM** : isolés par utilisateur (`user_id`)
- **Tâches** : partagées au sein de l'organisation (`org_id`)
- **Admin** : voit tous les utilisateurs de son organisation

---

## API

Documentation interactive disponible sur `/docs` (Swagger UI) ou `/redoc`.

### Exemples

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@therese.local&password=admin" \
  | jq -r '.access_token')

# Lister les conversations
curl -s http://localhost/api/chat/conversations \
  -H "Authorization: Bearer $TOKEN"

# Créer une tâche
curl -s -X POST http://localhost/api/tasks/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Préparer le conseil","priority":"high","status":"todo"}'

# Pipeline CRM
curl -s http://localhost/api/crm/pipeline/stats \
  -H "Authorization: Bearer $TOKEN"

# Calculer un ROI
curl -s -X POST http://localhost/api/calc/roi \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"investment":10000,"gain":15000,"period_months":12}'
```

---

## Déploiement production

### Variables d'environnement

| Variable | Description | Obligatoire |
|----------|-------------|:-----------:|
| `SECRET_KEY` | Clé de chiffrement app (32 hex) | oui |
| `JWT_SECRET` | Clé signature JWT (32 hex) | oui |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL | oui |
| `ENCRYPTION_KEY` | Clé Fernet pour chiffrement données | oui |
| `DOMAIN` | Domaine pour Caddy HTTPS | prod |
| `ANTHROPIC_API_KEY` | Clé API Claude | optionnel |
| `OPENAI_API_KEY` | Clé API OpenAI | optionnel |
| `GOOGLE_API_KEY` | Clé API Gemini | optionnel |
| `OLLAMA_URL` | URL serveur Ollama local | optionnel |

### Sécurité

- Tous les secrets sont générés via `openssl rand -hex 32`
- Mots de passe hashés en bcrypt (cost 12)
- JWT avec expiration configurable (défaut 1h)
- Chiffrement des clés API au repos (Fernet AES-128-CBC + HMAC-SHA256)
- Headers sécurité : HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff, CSP
- Rate limiting (SlowAPI) sur les endpoints sensibles
- Protection anti-injection de prompts (OWASP LLM Top 10)
- Audit trail complet (IP, action, user, timestamp)

---

## Tests

```bash
cd backend
pytest --cov=app
```

---

## Feuille de route

### Fait (v0.1.0 - mars 2026)
- [x] Auth JWT + RBAC (admin/manager/agent)
- [x] Chat multi-modèles avec streaming SSE
- [x] Templates prompts secteur public (10)
- [x] Dashboard admin (KPI, users, audit)
- [x] CRM (contacts, pipeline, activités)
- [x] Tâches (CRUD, filtres, priorités)
- [x] RGPD (export, anonymisation)
- [x] RAG documents (Qdrant)
- [x] 107 endpoints API documentés
- [x] Docker Compose déployable

### À venir
- [ ] Board de délibération (multi-advisors)
- [ ] Factures (génération PDF, suivi paiements)
- [ ] Email (IMAP/SMTP, Gmail OAuth)
- [ ] Calendrier (CalDAV, gestion événements)
- [ ] Skills (bibliothèque de compétences IA)
- [ ] Agents IA (atelier, missions)
- [ ] Voix (transcription audio)
- [ ] MCP (Model Context Protocol)

---

## Contribuer

Le projet est en alpha. Les contributions sont les bienvenues.

1. Fork le repo
2. Crée une branche (`git checkout -b feature/ma-feature`)
3. Commit (`git commit -m 'Ajout de ma feature'`)
4. Push (`git push origin feature/ma-feature`)
5. Ouvre une Pull Request

Pour signaler un bug ou proposer une fonctionnalité : [GitHub Issues](https://github.com/ludovicsanchez38-creator/Synoptia-THERESE-Server/issues)

Pour signaler une vulnérabilité : ludo@synoptia.fr

---

## Licence

[AGPL-3.0](LICENSE) - Utilisation libre, modifications redistribuées sous même licence.

## Auteur

**Ludovic Sanchez** - [Synoptïa](https://synoptia.fr)

Accompagnement et déploiement : ludo@synoptia.fr

> "Humain d'abord - IA en soutien"
