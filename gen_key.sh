#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${1:-whisper-api}"

echo "[+] Gerando API key..."
API_KEY=$(openssl rand -base64 48 | tr -d '\n' | tr '/+' '_-')

docker exec -i "$CONTAINER" redis-cli SET "api:keys:${API_KEY}" 1 >/dev/null

echo
echo "======================================"
echo "API KEY criada com sucesso!"
echo "Container : $CONTAINER"
echo "API KEY   : $API_KEY"
echo "======================================"
