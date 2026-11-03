#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../backend"
# Render supplies the current hostname even when a service name gets a suffix.
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-${RENDER_EXTERNAL_HOSTNAME:?Render hostname is missing}}"
for sipi_setting in DATABASE_URL DJANGO_SECRET_KEY FRONTEND_URL CSRF_TRUSTED_ORIGINS; do
  if [ -z "${!sipi_setting:-}" ]; then
    printf 'Missing required deployment setting: %s\n' "$sipi_setting" >&2
    exit 1
  fi
done
if [ "${ASSISTANT_PROVIDER:-}" != cloudflare ]; then
  printf 'This free deployment uses ASSISTANT_PROVIDER=cloudflare; local models need another host.\n' >&2
  exit 1
fi
# Free web services do not support pre-deploy jobs. One instance applies migrations
# before it begins listening. No model, worker loop or polling process runs here.
python manage.py migrate --noinput
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-10000}" \
  --worker-class gthread --workers 1 --threads 4 --timeout 300 \
  --access-logfile - --error-logfile - --forwarded-allow-ips "" \
  --no-control-socket
