# Therese Server

**Assistant IA multi-utilisateurs pour collectivites et PME francaises.**

Therese Server est la version serveur de [Therese](https://github.com/ludovicsanchez38-creator/Synoptia-THERESE), concue pour etre deployee on-premise dans les mairies (300-500 agents) et PME. Zero dependance cloud, donnees souveraines.

---

## Fonctionnalites

### Coeur

| Module | Description | Endpoints |
|--------|-------------|-----------|
| **Chat IA** | Conversations multi-modeles avec streaming SSE | 5 |
| **Auth JWT** | Authentification, roles (admin/manager/agent), RBAC | 9 |
| **Multi-tenant** | Isolation des donnees par organisation et utilisateur | - |
| **Charte IA** | Acceptation obligatoire avant premiere utilisation | 1 |
| **Templates** | 10 modeles de prompts secteur public (courrier, deliberation, note, synthese, communication, RH) | 5 |

### Productivite

| Module | Description | Endpoints |
|--------|-------------|-----------|
| **Taches** | Gestion de taches avec priorites et filtres (todo/en cours/termine) | 4 |
| **CRM** | Pipeline commercial, contacts, activites, livrables, import/export | 22 |
| **Commandes** | Commandes utilisateur personnalisees (v1 + v3 avec schema JSON) | 8 |
| **Calculateurs** | ROI, ICE, RICE, NPV, break-even | 6 |

### Administration

| Module | Description | Endpoints |
|--------|-------------|-----------|
| **Dashboard admin** | KPI, gestion utilisateurs, journal d'audit | 5 |
| **RGPD** | Export/anonymisation donnees, consentement, stats conformite | 8 |
| **Data** | Backup/restore, export conversations, import donnees | 12 |
| **Performance** | Metriques streaming, memoire, indexation, power management | 10 |
| **Personnalisation** | Templates perso, comportement LLM, visibilite features | 5 |

### IA et Recherche

| Module | Description | Endpoints |
|--------|-------------|-----------|
| **RAG** | Upload et indexation documents avec Qdrant (recherche semantique) | 5 |
| **Memory** | Contacts et projets en memoire semantique | 5 |
| **Multi-LLM** | Claude, GPT-4o, Gemini Flash, Mistral Large, Ollama (local) | - |

> **107 endpoints API** documentes via Swagger UI (`/docs`)

### Roles et permissions

| Role | Chat | Taches | CRM | Templates | Admin | RGPD |
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

## Demarrage rapide

### Prerequis

- Docker + Docker Compose
- Une cle API LLM (Anthropic, OpenAI, Google, ou Ollama local)

### Installation

```bash
# Cloner
git clone https://github.com/ludovicsanchez38-creator/Synoptia-THERESE-Server.git
cd Synoptia-THERESE-Server

# Configurer
cp .env.example .env
# Editer .env : secrets, cles API, domaine

# Lancer
docker compose up -d

# Premier admin cree automatiquement :
#   Email : admin@therese.local
#   Mot de passe : admin
#   (a changer immediatement)
```

L'application est accessible sur `http://localhost` (Caddy gere le HTTPS en production).

### Sans Docker (developpement)

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
|   |   +-- services/api/   # Clients API typees
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

Chaque requete est scopee automatiquement :
- **Conversations** : visibles uniquement par leur createur (`user_id`)
- **Contacts/CRM** : isoles par utilisateur (`user_id`)
- **Taches** : partagees au sein de l'organisation (`org_id`)
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

# Creer une tache
curl -s -X POST http://localhost/api/tasks/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Preparer le conseil","priority":"high","status":"todo"}'

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

## Deploiement production

### Variables d'environnement

| Variable | Description | Obligatoire |
|----------|-------------|:-----------:|
| `SECRET_KEY` | Cle de chiffrement app (32 hex) | oui |
| `JWT_SECRET` | Cle signature JWT (32 hex) | oui |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL | oui |
| `ENCRYPTION_KEY` | Cle Fernet pour chiffrement donnees | oui |
| `DOMAIN` | Domaine pour Caddy HTTPS | prod |
| `ANTHROPIC_API_KEY` | Cle API Claude | optionnel |
| `OPENAI_API_KEY` | Cle API OpenAI | optionnel |
| `GOOGLE_API_KEY` | Cle API Gemini | optionnel |
| `OLLAMA_URL` | URL serveur Ollama local | optionnel |

### Securite

- Tous les secrets sont generes via `openssl rand -hex 32`
- Mots de passe hashes en bcrypt (cost 12)
- JWT avec expiration configurable (defaut 1h)
- Headers securite : HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff
- Rate limiting (SlowAPI) sur les endpoints sensibles
- Audit trail complet (IP, action, user, timestamp)

---

## Feuille de route

### Fait (v0.1.0)
- [x] Auth JWT + RBAC (admin/manager/agent)
- [x] Chat multi-modeles avec streaming SSE
- [x] Templates prompts secteur public (10)
- [x] Dashboard admin (KPI, users, audit)
- [x] CRM (contacts, pipeline, activites)
- [x] Taches (CRUD, filtres, priorites)
- [x] RGPD (export, anonymisation)
- [x] RAG documents (Qdrant)
- [x] 107 endpoints API documentes
- [x] Docker Compose deployable

### A venir
- [ ] Board de deliberation (multi-advisors)
- [ ] Factures (generation PDF, suivi paiements)
- [ ] Email (IMAP/SMTP, Gmail OAuth)
- [ ] Calendrier (CalDAV, gestion evenements)
- [ ] Skills (bibliotheque de competences IA)
- [ ] Agents IA (atelier, missions)
- [ ] Voix (transcription audio)
- [ ] MCP (Model Context Protocol)

---

## Licence

[AGPL-3.0](LICENSE) - Utilisation libre, modifications redistribuees sous meme licence.

## Auteur

**Ludovic Sanchez** - [Synoptia](https://synoptia.fr)

> "Humain d'abord - IA en soutien"
