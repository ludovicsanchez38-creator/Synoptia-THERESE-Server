#!/bin/bash
# ============================================
# Therese Server - Backup complet
# PostgreSQL + Qdrant snapshots + uploads
# ============================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/home/ubuntu/therese-server/data/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS="${RETENTION_DAYS:-7}"
BACKUP_REMOTE="${BACKUP_REMOTE:-}"  # ex: rclone:s3-bucket/therese

mkdir -p "$BACKUP_DIR"

echo "$(date): Debut backup Therese Server..."

# --- PostgreSQL ---
PG_FILE="${BACKUP_DIR}/therese_pg_${TIMESTAMP}.sql.gz"
if docker exec therese-server-db-1 pg_dump -U therese therese 2>/dev/null | gzip > "$PG_FILE"; then
    echo "  PostgreSQL : OK ($(du -h "$PG_FILE" | cut -f1))"
else
    # Essayer avec l'ancien nom de conteneur
    docker exec therese-db pg_dump -U therese therese 2>/dev/null | gzip > "$PG_FILE" || {
        echo "  PostgreSQL : ECHEC"
        rm -f "$PG_FILE"
    }
    [ -f "$PG_FILE" ] && echo "  PostgreSQL : OK ($(du -h "$PG_FILE" | cut -f1))"
fi

# --- Qdrant snapshots ---
QDRANT_FILE="${BACKUP_DIR}/therese_qdrant_${TIMESTAMP}.snapshot.tar.gz"
if curl -sf http://localhost:6333/collections/therese-docs/snapshots -X POST > /dev/null 2>&1; then
    # Recuperer le dernier snapshot
    SNAPSHOT_NAME=$(curl -sf http://localhost:6333/collections/therese-docs/snapshots | python3 -c "import sys,json; snaps=json.load(sys.stdin)['result']; print(snaps[-1]['name'] if snaps else '')" 2>/dev/null || true)
    if [ -n "$SNAPSHOT_NAME" ]; then
        curl -sf "http://localhost:6333/collections/therese-docs/snapshots/${SNAPSHOT_NAME}" -o "$QDRANT_FILE"
        echo "  Qdrant     : OK ($(du -h "$QDRANT_FILE" | cut -f1))"
    else
        echo "  Qdrant     : SKIP (pas de snapshot)"
    fi
else
    echo "  Qdrant     : SKIP (service non disponible)"
fi

# --- Retention locale ---
find "$BACKUP_DIR" -name "therese_*" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
echo "  Retention  : fichiers > ${RETENTION_DAYS}j supprimes"

# --- Sync externe (optionnel) ---
if [ -n "$BACKUP_REMOTE" ] && command -v rclone &>/dev/null; then
    rclone copy "$BACKUP_DIR" "$BACKUP_REMOTE" --max-age "${RETENTION_DAYS}d" -q
    echo "  Remote     : synced vers $BACKUP_REMOTE"
fi

echo "$(date): Backup termine."
