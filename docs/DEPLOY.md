# Deploiement - Therese Server

Guide complet pour deployer Therese Server avec Docker.

## Prerequis

- **Docker** >= 24.0
- **Docker Compose** (plugin v2) >= 2.20
- **Espace disque** : 5 Go minimum (images Docker + modeles d'embeddings)
- **RAM** : 4 Go minimum (sentence-transformers charge un modele en memoire)
- **Ports** : 80 et 443 libres (Caddy), ou 8000/3000 en acces direct

### Installation de Docker (Ubuntu/Debian)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Se reconnecter pour appliquer le groupe
```

## Demarrage rapide

```bash
# 1. Cloner le projet
git clone git@github.com:ludovicsanchez38-creator/Synoptia-THERESE-Server.git therese-server
cd therese-server

# 2. Premier lancement (genere les secrets, lance tout)
chmod +x scripts/first-run.sh
./scripts/first-run.sh

# 3. C'est pret !
#    Frontend : http://votre-ip:3000
#    Backend  : http://votre-ip:8000/docs
#    Admin    : admin@therese.local / admin
```

## Configuration (.env)

Le fichier `.env` est cree automatiquement par `first-run.sh`. Variables principales :

| Variable | Description | Defaut |
|----------|-------------|--------|
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL | (genere) |
| `SECRET_KEY` | Cle secrete FastAPI | (genere) |
| `JWT_SECRET` | Secret JWT pour l'authentification | (genere) |
| `ENCRYPTION_KEY` | Cle Fernet pour le chiffrement des donnees | (genere) |
| `DEBUG` | Active les logs debug et /docs | `false` |
| `DOMAIN` | Domaine pour HTTPS (Caddy) | `therese.example.com` |
| `ANTHROPIC_API_KEY` | Cle API Anthropic (Claude) | (vide) |
| `MISTRAL_API_KEY` | Cle API Mistral | (vide) |
| `OPENAI_API_KEY` | Cle API OpenAI | (vide) |
| `GOOGLE_API_KEY` | Cle API Google (Gemini) | (vide) |

### Fournisseurs LLM

Au moins une cle API est necessaire pour que l'assistant fonctionne. Configurez celles que vous utilisez dans `.env`.

## Premier compte administrateur

Le service `seed` cree automatiquement au premier lancement :
- **Organisation** : "Organisation par defaut"
- **Admin** : `admin@therese.local` / `admin`

Changez ce mot de passe immediatement apres le premier login.

## Production avec HTTPS (Caddy)

### 1. Configurer le domaine

Editez `.env` :
```
DOMAIN=therese.mondomaine.fr
```

### 2. Mettre a jour le Caddyfile

Remplacez le contenu par :
```
therese.mondomaine.fr {
    # API backend
    handle /api/* {
        reverse_proxy backend:8000
    }

    handle /health* {
        reverse_proxy backend:8000
    }

    # Frontend
    handle {
        reverse_proxy frontend:3000
    }
}
```

### 3. DNS

Creez un enregistrement A pointant vers l'IP du serveur :
```
therese.mondomaine.fr  ->  A  ->  IP_DU_SERVEUR
```

### 4. Redemarrer Caddy

```bash
docker compose restart caddy
```

Caddy obtient automatiquement un certificat Let's Encrypt.

## Sauvegarde

### Base de donnees PostgreSQL

```bash
# Sauvegarde
docker compose exec db pg_dump -U therese therese > backup_$(date +%Y%m%d_%H%M%S).sql

# Restauration
cat backup_20260317.sql | docker compose exec -T db psql -U therese therese
```

### Donnees Qdrant

Les donnees Qdrant sont dans le volume Docker `therese-server_qdrant_data`.

```bash
# Sauvegarde du volume
docker run --rm -v therese-server_qdrant_data:/data -v $(pwd):/backup \
    alpine tar czf /backup/qdrant_backup_$(date +%Y%m%d).tar.gz /data

# Restauration
docker run --rm -v therese-server_qdrant_data:/data -v $(pwd):/backup \
    alpine tar xzf /backup/qdrant_backup_20260317.tar.gz -C /
```

### Script de sauvegarde complete

```bash
#!/bin/bash
# Sauvegarde quotidienne (a mettre dans un cron)
BACKUP_DIR="/home/ubuntu/backups/therese"
mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y%m%d_%H%M%S)

# PostgreSQL
docker compose exec -T db pg_dump -U therese therese | gzip > "$BACKUP_DIR/pg_${DATE}.sql.gz"

# Qdrant
docker run --rm -v therese-server_qdrant_data:/data -v "$BACKUP_DIR":/backup \
    alpine tar czf "/backup/qdrant_${DATE}.tar.gz" /data

# Nettoyage (garder 30 jours)
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete

echo "Sauvegarde terminee : $BACKUP_DIR"
```

## Monitoring

### Etat des services

```bash
# Statut de tous les conteneurs
docker compose ps

# Sante du backend
curl http://127.0.0.1:8000/health

# Sante detaillee (DB + Qdrant)
curl http://127.0.0.1:8000/health/services

# Logs en temps reel
docker compose logs -f

# Logs d'un service specifique
docker compose logs -f backend
docker compose logs -f db
```

### Surveillance de l'espace disque

```bash
# Taille des volumes Docker
docker system df -v

# Nettoyage des images inutilisees
docker image prune -f
```

## Mise a jour

```bash
cd /home/ubuntu/therese-server

# 1. Recuperer les modifications
git pull

# 2. Reconstruire et relancer
docker compose up -d --build

# 3. Verifier les logs
docker compose logs -f backend

# 4. Verifier la sante
curl http://127.0.0.1:8000/health
```

Pour une mise a jour sans interruption (si le serveur est en production) :

```bash
# Construire les nouvelles images
docker compose build

# Relancer un service a la fois
docker compose up -d --no-deps backend
docker compose up -d --no-deps frontend
```

## Architecture des services

```
                    [Internet]
                        |
                    [Caddy :80/:443]
                    /            \
            /api/*              /*
                |                |
        [Backend :8000]    [Frontend :3000]
            |       \
    [PostgreSQL]  [Qdrant]
        :5432      :6333
```

- **Caddy** : reverse proxy avec HTTPS automatique (Let's Encrypt)
- **Frontend** : application React servie en statique (serve)
- **Backend** : API FastAPI (Python)
- **PostgreSQL** : base de donnees relationnelle (utilisateurs, conversations, etc.)
- **Qdrant** : base vectorielle pour le RAG (recherche semantique)

## Depannage

### Le backend ne demarre pas

```bash
# Verifier les logs
docker compose logs backend

# Causes frequentes :
# - POSTGRES_PASSWORD different entre .env et la DB deja initialisee
#   Solution : docker compose down -v (ATTENTION : supprime les donnees)
# - Port 8000 deja utilise
#   Solution : lsof -i :8000
```

### Le seed ne s'execute pas

```bash
# Relancer manuellement
docker compose run --rm seed

# Verifier les logs
docker compose logs seed
```

### Erreur "sentence-transformers" au demarrage

Le premier demarrage telecharge le modele d'embeddings (~500 Mo). Cela peut prendre quelques minutes. Verifiez les logs du backend :

```bash
docker compose logs -f backend
```

### Reset complet (perte de toutes les donnees)

```bash
docker compose down -v
./scripts/first-run.sh
```
