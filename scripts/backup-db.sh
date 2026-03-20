#!/bin/bash
# Backup PostgreSQL Therese Server
BACKUP_DIR="/home/ubuntu/therese-server/data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/therese_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

# Dump via Docker
docker exec therese-db pg_dump -U therese therese | gzip > "$BACKUP_FILE"

# Garder les 7 derniers backups
ls -t "${BACKUP_DIR}"/therese_*.sql.gz | tail -n +8 | xargs -r rm

echo "$(date): Backup OK -> $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
