#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/create_basic_auth_user.sh USERNAME [DISPLAY_NAME]

Creates or updates one Basic Auth user and ensures the matching application
user row exists in SQLite.

Environment overrides:
  HTPASSWD_PATH  default: deployment/nginx/auth/.htpasswd
  APP_DB_PATH    default in compose: /data/garmin_ai_coach.db
  USE_COMPOSE    default: 1. Set to 0 to update APP_DB_PATH locally.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage >&2
  exit 2
fi

USERNAME="$1"
DISPLAY_NAME="${2:-$1}"
HTPASSWD_PATH="${HTPASSWD_PATH:-deployment/nginx/auth/.htpasswd}"
APP_DB_PATH="${APP_DB_PATH:-/data/garmin_ai_coach.db}"
USE_COMPOSE="${USE_COMPOSE:-1}"

if [[ "$USERNAME" =~ [[:space:]] || -z "$USERNAME" ]]; then
  echo "username must be non-empty and must not contain whitespace" >&2
  exit 2
fi

read -r -s -p "Password for ${USERNAME}: " PASSWORD
echo
read -r -s -p "Repeat password: " PASSWORD_REPEAT
echo

if [[ "$PASSWORD" != "$PASSWORD_REPEAT" ]]; then
  echo "passwords do not match" >&2
  exit 2
fi

if [[ -z "$PASSWORD" ]]; then
  echo "password must not be empty" >&2
  exit 2
fi

mkdir -p "$(dirname "$HTPASSWD_PATH")"
touch "$HTPASSWD_PATH"
chmod 600 "$HTPASSWD_PATH"

if command -v htpasswd >/dev/null 2>&1; then
  htpasswd -bB "$HTPASSWD_PATH" "$USERNAME" "$PASSWORD" >/dev/null
elif command -v openssl >/dev/null 2>&1; then
  HASHED_PASSWORD="$(printf '%s' "$PASSWORD" | openssl passwd -apr1 -stdin)"
  TMP_FILE="$(mktemp)"
  awk -F: -v username="$USERNAME" '$1 != username { print }' "$HTPASSWD_PATH" > "$TMP_FILE"
  printf '%s:%s\n' "$USERNAME" "$HASHED_PASSWORD" >> "$TMP_FILE"
  mv "$TMP_FILE" "$HTPASSWD_PATH"
else
  echo "install htpasswd or openssl to update ${HTPASSWD_PATH}" >&2
  exit 1
fi

if [[ "$USE_COMPOSE" == "1" ]]; then
  docker compose run --rm --no-deps --entrypoint python assistant_api \
    -m services.assistant_api.identity.users \
    --db-path "$APP_DB_PATH" \
    ensure-user \
    --username "$USERNAME" \
    --display-name "$DISPLAY_NAME"
else
  python -m services.assistant_api.identity.users \
    --db-path "$APP_DB_PATH" \
    ensure-user \
    --username "$USERNAME" \
    --display-name "$DISPLAY_NAME"
fi

echo "Basic Auth and application user are ready for ${USERNAME}."
