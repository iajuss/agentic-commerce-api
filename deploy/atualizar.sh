#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ "$(git branch --show-current)" != "main" ]]; then
    printf 'O clone de produção deve estar na branch main.\n' >&2
    exit 1
fi

git pull --ff-only
.venv/bin/python -m pip install -r requirements.txt
sudo systemctl restart agentic-commerce-api

for tentativa in {1..10}; do
    if curl -fsS http://127.0.0.1:8000/health; then
        printf '\n'
        exit 0
    fi
    sleep 1
done

printf 'A API não respondeu em 127.0.0.1:8000/health.\n' >&2
exit 1
