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
echo "Локальный Django: $DB_ENGINE. Аккаунты из другой базы автоматически не переносятся."
backend/.venv/bin/python backend/manage.py migrate --noinput
sipi_backend_pid=""
sipi_frontend_pid=""
sipi_ollama_pid=""
sipi_chat_pid=""
sipi_image_pid=""
sipi_cleanup() {
  trap - EXIT INT TERM
  if [ -n "$sipi_backend_pid" ]; then kill "$sipi_backend_pid" 2>/dev/null || true; fi
  if [ -n "$sipi_frontend_pid" ]; then kill "$sipi_frontend_pid" 2>/dev/null || true; fi
  for sipi_pid in "$sipi_chat_pid" "$sipi_image_pid" "$sipi_ollama_pid"; do
    if [ -n "$sipi_pid" ]; then kill "$sipi_pid" 2>/dev/null || true; fi
  done
  wait 2>/dev/null || true
}
trap sipi_cleanup EXIT INT TERM
# Start an existing local model installation; downloading is explicit in setup-ai.sh.
if [ -x .runtime/ollama ]; then sipi_ollama="$PWD/.runtime/ollama"
elif [ -x .runtime/bin/ollama ]; then sipi_ollama="$PWD/.runtime/bin/ollama"
else sipi_ollama=$(command -v ollama || true); fi
export ASSISTANT_OLLAMA_URL="${ASSISTANT_OLLAMA_URL:-http://127.0.0.1:11434}"
if [ -n "$sipi_ollama" ] && ! curl -fsS --max-time 2 "$ASSISTANT_OLLAMA_URL/api/tags" >/dev/null 2>&1; then
  mkdir -p .runtime
  OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$PWD/.runtime/models" OLLAMA_NO_CLOUD=1 "$sipi_ollama" serve > .runtime/ollama.log 2>&1 &
  sipi_ollama_pid=$!
fi
if [ -d .runtime/image-model ]; then
  export ASSISTANT_IMAGES_ENABLED="${ASSISTANT_IMAGES_ENABLED:-true}"
  export ASSISTANT_IMAGE_MODEL="${ASSISTANT_IMAGE_MODEL:-$PWD/.runtime/image-model}"
fi
backend/.venv/bin/python backend/manage.py assistant_worker --kind chat &
sipi_chat_pid=$!
if [ "${ASSISTANT_IMAGES_ENABLED:-false}" = true ]; then
  backend/.venv/bin/python backend/manage.py assistant_worker --kind logo &
  sipi_image_pid=$!
fi
backend/.venv/bin/python backend/manage.py runserver 127.0.0.1:8000 --noreload &
sipi_backend_pid=$!
(cd frontend && exec node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3000) &
sipi_frontend_pid=$!
echo "Сипи: http://127.0.0.1:3000 · Админка: http://127.0.0.1:8000/admin/"
if [ "$EMAIL_BACKEND" = django.core.mail.backends.console.EmailBackend ]; then
  echo "Коды подтверждения появятся ниже, в выводе Django."
else
  echo "Доставка кодов подтверждения настроена через EMAIL_BACKEND."
fi
# Exit if either service fails, and stop the other one as well.
while kill -0 "$sipi_backend_pid" 2>/dev/null && kill -0 "$sipi_frontend_pid" 2>/dev/null; do
  sleep 1
done
exit 1
