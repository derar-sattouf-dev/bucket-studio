#!/usr/bin/env bash
# Create .env from .env.example with freshly generated secrets.
# Usage: ./scripts/init-env.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ -f .env ]; then
    echo "✗ .env already exists — remove it first if you really want to regenerate it." >&2
    exit 1
fi
command -v openssl > /dev/null || { echo "✗ openssl is required" >&2; exit 1; }

secret() { openssl rand -hex "$1"; }

admin_password="$(secret 12)"
step_up_password="$(secret 12)"

cp .env.example .env
chmod 600 .env

set_var() {  # set_var NAME VALUE — replaces the NAME=… line in .env, or appends it
    local tmp
    tmp="$(mktemp)"
    awk -v name="$1" -v value="$2" -F= '
        $1 == name { print name "=" value; found = 1; next } { print }
        END { if (!found) print name "=" value }' .env > "$tmp"
    mv "$tmp" .env
    chmod 600 .env
}

set_var JWT_SECRET "$(secret 32)"
set_var AUTH_USERNAME admin
set_var AUTH_PASSWORD "$admin_password"
set_var ADMIN_PASSWORD "$step_up_password"
set_var S3_ACCESS_KEY "bucketstudio"
set_var S3_SECRET_KEY "$(secret 20)"

cat <<MSG
✓ Created .env with random secrets.

  Sign in:         admin / ${admin_password}
  Admin password:  ${step_up_password}   (asked for sensitive actions)

Start the development stack:
  docker compose --profile dev up --build
Then open http://localhost:5173
MSG
