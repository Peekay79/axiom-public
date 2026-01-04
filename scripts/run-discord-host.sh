#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=".env.discord"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.discord.example -> .env.discord and fill DISCORD_TOKEN."
  exit 1
fi

set -a; source "$ENV_FILE"; set +a

# Prefer existing venv the project already uses for Discord
PY="${PYTHON:-./venv-discord/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "Python venv for Discord not found at ./venv-discord/bin/python"
  echo "Create it (example): python3 -m venv venv-discord && ./venv-discord/bin/pip install -r requirements.txt"
  exit 1
fi

echo "→ Running smoke checks..."
bash scripts/smoke-discord-host.sh

echo "→ Launching Discord bot…"
exec "$PY" startup_discord_interface.py