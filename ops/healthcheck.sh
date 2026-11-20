#!/usr/bin/env bash
# Restart the production backend if it stops answering /health.
# Docker restarts crashed containers (restart: unless-stopped) but not hung ones; run this from cron:
#   */5 * * * * /path/to/repo/ops/healthcheck.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:3000/api/health}"
LOG_FILE="${LOG_FILE:-/var/log/bucket-studio-healthcheck.log}"
MAX_LOG_LINES=1000

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"; }

if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt "$MAX_LOG_LINES" ]; then
    tail -n $((MAX_LOG_LINES / 2)) "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

compose() { docker compose --project-directory "$REPO_DIR" --profile prod "$@"; }

container="$(compose ps -q backend)"
if [ -z "$container" ] || [ "$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null)" != "true" ]; then
    log "[WARN] backend is not running — starting"
    compose up -d backend >> "$LOG_FILE" 2>&1
    exit 0
fi

http_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$HEALTH_URL" || true)"
if [ "$http_code" != "200" ]; then
    log "[WARN] health check failed (HTTP ${http_code:-none}) — restarting backend"
    compose restart backend >> "$LOG_FILE" 2>&1
else
    log "[OK] backend healthy"
fi
