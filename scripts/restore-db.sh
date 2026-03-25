#!/bin/bash
# ============================================
# Therese Server - Restauration PostgreSQL
# Usage: ./restore-db.sh <fichier.sql.gz>
# ============================================

set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo "Backups disponibles :"
    ls -lht /home/ubuntu/therese-server/data/backups/therese_pg_*.sql.gz 2>/dev/null || echo "  Aucun backup trouve"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Erreur: fichier '$BACKUP_FILE' introuvable"
    exit 1
fi

echo "ATTENTION: Cette operation va REMPLACER la base de donnees actuelle."
echo "Fichier: $BACKUP_FILE"
read -p "Confirmer ? (oui/non) " -r
if [ "$REPLY" != "oui" ]; then
    echo "Annule."
    exit 0
fi

# Creer un backup de securite avant restauration
SAFETY_DIR="/home/ubuntu/therese-server/data/backups"
SAFETY_FILE="${SAFETY_DIR}/therese_pg_pre_restore_$(date +%Y%m%d_%H%M%S).sql.gz"
docker exec therese-server-db-1 pg_dump -U therese therese 2>/dev/null | gzip > "$SAFETY_FILE" || \
    docker exec therese-db pg_dump -U therese therese 2>/dev/null | gzip > "$SAFETY_FILE"
echo "Backup de securite: $SAFETY_FILE"

# Restauration
echo "Restauration en cours..."
gunzip -c "$BACKUP_FILE" | docker exec -i therese-server-db-1 psql -U therese -d therese 2>/dev/null || \
    gunzip -c "$BACKUP_FILE" | docker exec -i therese-db psql -U therese -d therese

echo "Restauration terminee. Redemarrez le backend : docker compose restart backend"
