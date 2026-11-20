#!/usr/bin/env bash
# Load a handful of public-domain / CC0 sample photos into a running Bucket Studio instance,
# using the "Import from URLs" API. Handy for trying the app or taking screenshots.
#
# Usage: ./scripts/seed-demo.sh [API_URL] [USERNAME] [PASSWORD]
#   API_URL defaults to http://localhost:8000 (dev); use http://localhost:3000/api for the prod stack.
#   USERNAME / PASSWORD default to AUTH_USERNAME / AUTH_PASSWORD from .env.
#
# Image credits: Wikimedia Commons — Cleveland Museum of Art Open Access (CC0) and other CC0 /
# public-domain uploads. See docs/screenshots/CREDITS.md.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

env_value() { [ -f .env ] && sed -n "s/^$1=//p" .env | tail -n 1 || true; }

API_URL="${1:-http://localhost:8000}"
USERNAME="${2:-$(env_value AUTH_USERNAME)}"
PASSWORD="${3:-$(env_value AUTH_PASSWORD)}"
[ -n "$USERNAME" ] && [ -n "$PASSWORD" ] || { echo "✗ pass USERNAME and PASSWORD (or set them in .env)" >&2; exit 1; }

commons() { echo "https://commons.wikimedia.org/wiki/Special:FilePath/$1?width=1600"; }

json() { python3 -c 'import json,sys; print(json.dumps(dict(zip(sys.argv[1::2], sys.argv[2::2]))))' "$@"; }

token="$(curl -fsS -X POST "$API_URL/auth/login" -H 'Content-Type: application/json' \
    -d "$(json username "$USERNAME" password "$PASSWORD")" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')"

import_urls() {  # import_urls FOLDER URL...
    local folder="$1"; shift
    local body
    body="$(python3 -c 'import json,sys; print(json.dumps({"folder": sys.argv[1], "urls": sys.argv[2:]}))' "$folder" "$@")"
    curl -fsS -X POST "$API_URL/imports/" -H "Authorization: Bearer $token" -H 'Content-Type: application/json' -d "$body" \
        | python3 -c 'import json,sys; r=json.load(sys.stdin); print("  %s: %d imported, %d failed" % (sys.argv[1], len(r["imported"]), len(r["failed"]))); [print("   x", f["url"], "-", f["error"]) for f in r["failed"]]' "$folder"
}

echo "Importing sample images into $API_URL …"
import_urls "ceramics/" \
    "$(commons 'Chantilly_Porcelain_Factory_(French)_-_Teapot_-_1944.228.1.a_-_Cleveland_Museum_of_Art.jpg')" \
    "$(commons 'Davenport_Pottery_and_Porcelain_Factory_(British)_-_Teapot_-_1940.10.a_-_Cleveland_Museum_of_Art.jpg')" \
    "$(commons 'PlainMug.jpg')"
import_urls "gear/" \
    "$(commons 'Fashion-wristwatch-time-watch-1_(24325510005).jpg')" \
    "$(commons 'Adapted_Lens_on_Mirrorless_Camera.jpg')" \
    "$(commons 'Military_backpack_01.jpg')"
import_urls "furniture/" \
    "$(commons "Consumer's_Rest_chair,_V%26A_Museum_01.jpg")"

echo "✓ Done. Open the Images page to process them."
