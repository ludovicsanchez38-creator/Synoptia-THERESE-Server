#!/bin/bash
# Backup PostgreSQL Therese Server
# Usage : ./backup-db.sh
# Cron  : 0 2 * * * /home/ubuntu/therese-server/scripts/backup-db.sh >> /var/log/therese-backup.log 2>&1
#
# Variables d'environnement optionnelles :
#   BACKUP_REMOTE  - remote rclone (ex: "b2:therese-backups" ou "s3:my-bucket/therese")
#   BACKUP_RETAIN  - nombre de backups locaux a garder (defaut: 7)
#   POSTGRES_USER  - user PostgreSQL (defaut: therese)
#   POSTGRES_DB    - nom de la base (defaut: therese)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/therese_${TIMESTAMP}.sql.gz"
RETAIN=${BACKUP_RETAIN:-7}
PG_USER=${POSTGRES_USER:-therese}
PG_DB=${POSTGRES_DB:-therese}

mkdir -p "$BACKUP_DIR"

# --- 1. Dump PostgreSQL ---
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Debut backup..."

if docker exec therese-db pg_dump -U "$PG_USER" "$PG_DB" | gzip > "$BACKUP_FILE"; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Dump OK : $BACKUP_FILE ($SIZE)"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERREUR : dump PostgreSQL echoue" >&2
    exit 1
fi

# --- 2. Upload externe (si rclone configure) ---
if [ -n "${BACKUP_REMOTE:-}" ] && command -v rclone &> /dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Upload vers $BACKUP_REMOTE..."
    if rclone copy "$BACKUP_FILE" "$BACKUP_REMOTE/" --progress; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Upload OK"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ATTENTION : upload echoue (backup local conserve)" >&2
    fi

    # Nettoyage remote (garder RETAIN derniers)
    if [ "$RETAIN" -gt 0 ]; then
        rclone lsf "$BACKUP_REMOTE/" --files-only | sort -r | tail -n +$((RETAIN + 1)) | while read -r old; do
            rclone deletefile "$BACKUP_REMOTE/$old" 2>/dev/null && echo "  Remote supprime : $old"
        done
    fi
else
    if [ -n "${BACKUP_REMOTE:-}" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ATTENTION : BACKUP_REMOTE defini mais rclone absent" >&2
    fi
fi

# --- 3. Rotation locale ---
REMOVED=$(ls -t "${BACKUP_DIR}"/therese_*.sql.gz 2>/dev/null | tail -n +$((RETAIN + 1)) | wc -l)
ls -t "${BACKUP_DIR}"/therese_*.sql.gz 2>/dev/null | tail -n +$((RETAIN + 1)) | xargs -r rm
if [ "$REMOVED" -gt 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Rotation : $REMOVED ancien(s) backup(s) supprime(s)"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup termine."
