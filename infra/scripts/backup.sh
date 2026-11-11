#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

on_error() {
  local status=$?
  trap - ERR
  log "ERROR: резервное копирование завершилось с кодом ${status}."
  exit "$status"
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env.server}"

[[ -f "$ENV_FILE" ]] || fail "Не найден файл настроек: $ENV_FILE"

# .env.server должен содержать обычные shell-совместимые KEY=value.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${DB_NAME:?В ENV_FILE не задан DB_NAME}"
: "${DB_USER:?В ENV_FILE не задан DB_USER}"
: "${R2_ACCOUNT_ID:?В ENV_FILE не задан R2_ACCOUNT_ID}"
: "${R2_ACCESS_KEY_ID:?В ENV_FILE не задан R2_ACCESS_KEY_ID}"
: "${R2_SECRET_ACCESS_KEY:?В ENV_FILE не задан R2_SECRET_ACCESS_KEY}"
: "${R2_BUCKET:?В ENV_FILE не задан R2_BUCKET}"

BACKUP_DB_MODE="${BACKUP_DB_MODE:-host}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
R2_PREFIX="${R2_PREFIX:-team-control/postgres}"
DB_PORT="${DB_PORT:-5432}"

[[ "$BACKUP_DB_MODE" == "host" || "$BACKUP_DB_MODE" == "docker" ]] || fail "BACKUP_DB_MODE должен быть host или docker."
[[ "$DB_NAME" =~ ^[A-Za-z0-9_-]+$ ]] || fail "DB_NAME содержит неподдерживаемые символы."
[[ "$R2_BUCKET" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] || fail "Проверь имя R2_BUCKET."
[[ "$R2_PREFIX" =~ ^[A-Za-z0-9/_-]+$ ]] || fail "R2_PREFIX может содержать только латинские буквы, цифры, /, _ и -."
[[ "$R2_PREFIX" != /* && "$R2_PREFIX" != */ && "$R2_PREFIX" != *//* ]] || fail "R2_PREFIX не должен начинаться/заканчиваться на / или содержать //."
[[ "$BACKUP_RETENTION_DAYS" =~ ^[1-9][0-9]*$ ]] || fail "BACKUP_RETENTION_DAYS должен быть положительным целым числом."

for command_name in rclone sha256sum awk tr grep; do
  command -v "$command_name" >/dev/null 2>&1 || fail "Не найдена команда $command_name."
done

if [[ "$BACKUP_DB_MODE" == "host" ]]; then
  : "${DB_HOST:?В ENV_FILE не задан DB_HOST}"
  : "${DB_PASSWORD:?В ENV_FILE не задан DB_PASSWORD}"
  for command_name in pg_dump psql; do
    command -v "$command_name" >/dev/null 2>&1 || fail "Не найдена команда $command_name."
  done
  export PGHOST="$DB_HOST"
  export PGPORT="$DB_PORT"
  export PGDATABASE="$DB_NAME"
  export PGUSER="$DB_USER"
  export PGPASSWORD="$DB_PASSWORD"
  export PGSSLMODE="${DB_SSLMODE:-prefer}"
  export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"
else
  command -v docker >/dev/null 2>&1 || fail "Для BACKUP_DB_MODE=docker требуется Docker Compose."
  docker compose version >/dev/null 2>&1 || fail "Docker Compose недоступен."
  compose_args=(--env-file "$ENV_FILE" -f "$REPO_ROOT/compose.server.yaml" -f "$REPO_ROOT/compose.server-db.yaml")
fi

# Конфигурация R2 задаётся через окружение; ключи не сохраняются в rclone.conf.
export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
export RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export RCLONE_CONFIG_R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
export RCLONE_CONFIG_R2_REGION=auto
export RCLONE_CONFIG_R2_ACL=private
export RCLONE_CONFIG_R2_NO_CHECK_BUCKET=true

rclone_version="$(rclone version | awk 'NR == 1 {sub(/^rclone v/, ""); print $1}')"
[[ "$rclone_version" =~ ^([0-9]+)\.([0-9]+) ]] || fail "Не удалось определить версию rclone."
rclone_major="${BASH_REMATCH[1]}"
rclone_minor="${BASH_REMATCH[2]}"
(( rclone_major > 1 || (rclone_major == 1 && rclone_minor >= 59) )) || fail "Нужен rclone версии 1.59 или новее."

db_psql() {
  local database="$1"
  local query="$2"
  if [[ "$BACKUP_DB_MODE" == "docker" ]]; then
    docker compose "${compose_args[@]}" exec -T db psql -X -w -qAt -U "$DB_USER" -d "$database" -c "$query"
  else
    psql -X -w -qAt -d "$database" -c "$query"
  fi
}

db_pg_dump_version() {
  if [[ "$BACKUP_DB_MODE" == "docker" ]]; then
    docker compose "${compose_args[@]}" exec -T db pg_dump --version | awk '{print $3}'
  else
    pg_dump --version | awk '{print $3}'
  fi
}

db_pg_dump() {
  if [[ "$BACKUP_DB_MODE" == "docker" ]]; then
    docker compose "${compose_args[@]}" exec -T db pg_dump --format=custom --no-owner --no-acl -U "$DB_USER" --dbname="$DB_NAME"
  else
    pg_dump --format=custom --no-owner --no-acl --dbname="$DB_NAME"
  fi
}

pg_dump_version="$(db_pg_dump_version)"
server_version="$(db_psql postgres 'SHOW server_version')"
[[ -n "$pg_dump_version" && -n "$server_version" ]] || fail "Не удалось определить версии PostgreSQL."
pg_dump_major="${pg_dump_version%%.*}"
server_major="${server_version%%.*}"
[[ "$pg_dump_major" =~ ^[0-9]+$ && "$server_major" =~ ^[0-9]+$ ]] || fail "Не удалось разобрать версии PostgreSQL."
(( pg_dump_major >= server_major )) || fail "pg_dump версии $pg_dump_version старее сервера PostgreSQL $server_version."

stamp="$(date -u '+%Y%m%dT%H%M%SZ')"
safe_db_name="$(printf '%s' "$DB_NAME" | tr -c 'A-Za-z0-9_-' '_')"
base_name="postgres-${safe_db_name}-${stamp}-$$.dump"
remote_dir="R2:$R2_BUCKET/$R2_PREFIX/$DB_NAME"
remote_file="$remote_dir/$base_name"

trap on_error ERR

log "Проверяю подключения к PostgreSQL и Cloudflare R2."
db_psql "$DB_NAME" 'SELECT 1' >/dev/null
rclone mkdir "$remote_dir"
rclone lsf "$remote_dir" >/dev/null

log "Создаю custom dump и отправляю поток напрямую в R2. Полный архив на локальный диск не записывается."
# Один параллельный multipart chunk 8 MiB; streaming cutoff ограничивает буфер маленьких объектов.
db_pg_dump |
  rclone --buffer-size 0 --transfers 1 --s3-upload-concurrency 1 \
    --s3-chunk-size 8M --streaming-upload-cutoff 1M \
    rcat "$remote_file"

remote_listing="$(rclone ls "$remote_dir")"
remote_size="$(awk -v target="$base_name" '$2 == target {print $1; exit}' <<< "$remote_listing")"
[[ "$remote_size" =~ ^[0-9]+$ ]] && (( remote_size > 0 )) || fail "Объект в R2 отсутствует или пуст."

# Сверяем SHA-256 полного объекта, прочитанного обратно из R2. Временный архив не создаётся.
remote_hash="$(rclone --buffer-size 0 cat "$remote_file" | sha256sum | awk '{print $1}')"
[[ "$remote_hash" =~ ^[a-f0-9]{64}$ ]] || fail "Не удалось вычислить SHA-256 загруженного объекта."

printf '%s  %s\n' "$remote_hash" "$base_name" |
  rclone --buffer-size 0 rcat "$remote_file.sha256"

metadata="$(mktemp)"
cleanup() {
  [[ -z "${metadata:-}" ]] || rm -f -- "$metadata"
}
trap cleanup EXIT
{
  printf 'created_at_utc=%s\n' "$stamp"
  printf 'database=%s\n' "$DB_NAME"
  printf 'postgres_server_version=%s\n' "$server_version"
  printf 'pg_dump_version=%s\n' "$pg_dump_version"
  printf 'rclone_version=%s\n' "$rclone_version"
  printf 'format=custom\n'
  printf 'size_bytes=%s\n' "$remote_size"
  printf 'sha256=%s\n' "$remote_hash"
  printf 'storage=Cloudflare R2\n'
} > "$metadata"
rclone --buffer-size 0 rcat "$remote_file.meta" < "$metadata"
rm -f -- "$metadata"
metadata=""
trap on_error ERR

# Не удаляем старые копии, пока архив и обе sidecar-записи не появились в R2.
uploaded_objects="$(rclone lsf "$remote_dir" --files-only)"
grep -Fxq "$base_name" <<< "$uploaded_objects" || fail "Не найден архив в R2 после загрузки."
grep -Fxq "$base_name.sha256" <<< "$uploaded_objects" || fail "Не найдена SHA-256 контрольная сумма в R2."
grep -Fxq "$base_name.meta" <<< "$uploaded_objects" || fail "Не найданы метаданные копии в R2."

# Ротация ограничена каталогом конкретной БД; удаляются только объекты старше retention.
rclone delete --min-age "${BACKUP_RETENTION_DAYS}d" "$remote_dir"

log "Резервная копия загружена и проверена в R2: $base_name ($remote_size bytes)."
log "Хранение: ${BACKUP_RETENTION_DAYS} дней. Полный архив на локальный диск не записывался."
