#!/bin/sh
# Start the real Django API and Next.js UI without Docker.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v npm >/dev/null 2>&1; then
  for sipi_candidate in "$HOME"/.nvm/versions/node/*/bin; do
    if [ -x "$sipi_candidate/node" ] && [ -f "$sipi_candidate/npm" ]; then
      PATH="$sipi_candidate:$PATH"
    fi
  done
  export PATH
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "Нужен Node.js 20.9+ (рекомендуется 24 LTS): https://nodejs.org/" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "Нужен Python 3.11 или новее." >&2
  exit 1
fi
# This is a shell env file under the user's control; it is never served to the browser.
if [ -f backend/.env ]; then
  set -a
  . ./backend/.env
  set +a
fi
# Fail before dependency installation, migrations or workers if a server is running.
python3 scripts/local_dev.py check
if [ ! -x backend/.venv/bin/python ]; then
  python3 -m venv backend/.venv
fi
if ! backend/.venv/bin/python -c "import django, psycopg2, gunicorn, whitenoise" >/dev/null 2>&1; then
  backend/.venv/bin/python -m pip install -r backend/requirements.txt
fi
if [ ! -d frontend/node_modules/next ]; then
  (cd frontend && npm ci)
fi
export DB_ENGINE="${DB_ENGINE:-sqlite}"
if [ "$DB_ENGINE" = sqlite ]; then
  export DB_NAME="${DB_NAME:-$PWD/backend/local.sqlite3}"
fi
export EMAIL_BACKEND="${EMAIL_BACKEND:-django.core.mail.backends.console.EmailBackend}"
export FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:3000}"
export DJANGO_API_URL="${DJANGO_API_URL:-http://127.0.0.1:8000}"
# Reuse an already-running model server; only a server started here is stopped here.
if [ -x .runtime/ollama ]; then sipi_ollama="$PWD/.runtime/ollama"
elif [ -x .runtime/bin/ollama ]; then sipi_ollama="$PWD/.runtime/bin/ollama"
else sipi_ollama=$(command -v ollama || true); fi
export SIPI_OLLAMA_BIN="$sipi_ollama"
export ASSISTANT_OLLAMA_URL="${ASSISTANT_OLLAMA_URL:-http://127.0.0.1:11434}"
if [ -d .runtime/image-model ]; then
  export ASSISTANT_IMAGES_ENABLED="${ASSISTANT_IMAGES_ENABLED:-true}"
  export ASSISTANT_IMAGE_MODEL="${ASSISTANT_IMAGE_MODEL:-$PWD/.runtime/image-model}"
fi
# The supervisor owns separate process groups, including Next.js child processes.
echo "Локальный Django: $DB_ENGINE. Аккаунты из другой базы автоматически не переносятся."
exec backend/.venv/bin/python -u scripts/local_dev.py run
