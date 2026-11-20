#!/usr/bin/env bash
# Optional host housekeeping for a small single-server deployment. Run as root from cron, e.g.:
#   0 4 * * * /path/to/repo/ops/cleanup.sh
# Container logs are already size-capped by docker-compose (json-file max-size/max-file).
set -euo pipefail

LOG_FILE="${LOG_FILE:-/var/log/bucket-studio-cleanup.log}"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"; }

log "--- cleanup started ---"

# Remove dangling images / build cache left behind by `docker compose up --build`
docker image prune -f >> "$LOG_FILE" 2>&1
docker builder prune -f --filter "until=168h" >> "$LOG_FILE" 2>&1
log "[docker] pruned dangling images and build cache older than 7 days"

# Keep the systemd journal bounded
if command -v journalctl > /dev/null; then
    journalctl --vacuum-time=7d >> "$LOG_FILE" 2>&1
    log "[journal] vacuumed entries older than 7 days"
fi

log "--- cleanup done ---"
