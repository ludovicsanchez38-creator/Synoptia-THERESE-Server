#!/bin/bash
# ===========================================
# Therese Server - Premier lancement
#
# Ce script :
# 1. Copie .env.example vers .env si necessaire
# 2. Genere les secrets (SECRET_KEY, JWT_SECRET, ENCRYPTION_KEY)
# 3. Lance docker compose
# 4. Attend que le backend soit operationnel
# 5. Affiche les identifiants admin
# ===========================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "==========================================="
echo "  Therese Server - Premier lancement"
echo "==========================================="
echo ""

# --- 1. Fichier .env ---
if [ ! -f .env ]; then
    if [ ! -f .env.example ]; then
        echo "ERREUR : .env.example introuvable dans $PROJECT_DIR"
        exit 1
    fi
    cp .env.example .env
    echo "[OK] .env cree depuis .env.example"
else
    echo "[INFO] .env existe deja, conservation des valeurs actuelles"
fi

# --- 2. Generation des secrets ---
generate_secret() {
    openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))"
}

generate_fernet_key() {
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || \
    python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
}

# Remplacer les valeurs par defaut dans .env
update_env() {
    local key="$1"
    local old_pattern="$2"
    local new_value="$3"

    if grep -q "${key}=${old_pattern}" .env 2>/dev/null; then
        # Utiliser un separateur qui ne risque pas de confliter
        sed -i "s|${key}=${old_pattern}|${key}=${new_value}|" .env
        echo "[OK] ${key} genere"
    else
        echo "[INFO] ${key} deja configure"
    fi
}

SECRET=$(generate_secret)
JWT=$(generate_secret)
PG_PASS=$(generate_secret | head -c 24)

update_env "SECRET_KEY" "changeme_generate_with_openssl_rand_hex_32" "$SECRET"
update_env "JWT_SECRET" "changeme_generate_with_openssl_rand_hex_32" "$JWT"
update_env "POSTGRES_PASSWORD" "changeme_en_production" "$PG_PASS"

# Fernet (necessite le module cryptography)
FERNET=$(generate_fernet_key)
update_env "ENCRYPTION_KEY" "changeme_generate_with_python_fernet" "$FERNET"

echo ""

# --- 3. Verification Docker ---
if ! command -v docker &>/dev/null; then
    echo "ERREUR : Docker n'est pas installe."
    echo "  Installation : https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo "ERREUR : Docker Compose (plugin) n'est pas installe."
    echo "  Installation : https://docs.docker.com/compose/install/"
    exit 1
fi

# --- 4. Lancement ---
echo "Construction et lancement des services..."
echo ""
docker compose up -d --build

# --- 5. Attente du backend ---
echo ""
echo "Attente du backend (peut prendre 1-2 min au premier lancement)..."
MAX_WAIT=120
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "[OK] Backend operationnel"
        break
    fi
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    echo "  Attente... (${ELAPSED}s)"
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo ""
    echo "ATTENTION : le backend n'a pas repondu dans les ${MAX_WAIT}s."
    echo "  Verifiez les logs : docker compose logs -f backend"
    exit 1
fi

# --- 6. Seed (le service seed s'execute automatiquement) ---
echo ""
echo "Attente de l'initialisation de la base (seed)..."
sleep 10
docker compose logs seed 2>/dev/null | tail -5

# --- 7. Resume ---
echo ""
echo "==========================================="
echo "  Therese Server est operationnel !"
echo "==========================================="
echo ""
echo "  Frontend  : http://127.0.0.1:3000"
echo "  Backend   : http://127.0.0.1:8000"
echo "  API Docs  : http://127.0.0.1:8000/docs"
echo "  Health    : http://127.0.0.1:8000/health"
echo ""
echo "  Compte administrateur :"
echo "    Email : admin@therese.local"
echo "    Mot de passe : admin"
echo ""
echo "  IMPORTANT : changez le mot de passe admin immediatement !"
echo ""
echo "  Pour configurer un domaine avec HTTPS :"
echo "    1. Editez DOMAIN dans .env"
echo "    2. Editez le Caddyfile"
echo "    3. docker compose restart caddy"
echo ""
echo "  Logs : docker compose logs -f"
echo "==========================================="
