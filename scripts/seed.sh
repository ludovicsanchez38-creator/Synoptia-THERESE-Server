#!/bin/bash
# ===========================================
# Therese Server - Script de seed
# Cree l'organisation par defaut et l'admin
# ===========================================

set -e

echo "=== Therese Server - Initialisation ==="

# Attendre que la base de donnees soit prete
echo "Attente de la base de donnees..."
MAX_RETRIES=30
RETRY=0
until python -c "
import asyncio
from app.models.database import init_db
asyncio.run(init_db())
print('Base de donnees prete')
" 2>/dev/null; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
        echo "ERREUR : la base de donnees n'est pas disponible apres ${MAX_RETRIES} tentatives"
        exit 1
    fi
    echo "  Tentative $RETRY/$MAX_RETRIES..."
    sleep 2
done

# Lancer le seed
echo "Lancement du seed..."
cd /app
python -m app.auth.seed

echo "=== Initialisation terminee ==="
