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

# Файл должен содержать обычные shell-совместимые KEY=value, как .env.server.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${DB_HOST:?В ENV_FILE не задан DB_HOST}"
: "${DB_PORT:=5432}"
: "${DB_NAME:?В ENV_FILE не задан DB_NAME}"
: "${DB_USER:?В ENV_FILE не задан DB_USER}"
: "${DB_PASSWORD:?В ENV_FILE не задан DB_PASSWORD}"
: "${BACKUP_DIR:?Задай BACKUP_DIR как точку монтирования отдельного хранилища}"

[[ "$DB_NAME" =~ ^[A-Za-z0-9_-]+$ ]] || fail "DB_NAME содержит неподдерживаемые символы."
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
[[ "$BACKUP_RETENTION_DAYS" =~ ^[1-9][0-9]*$ ]] || fail "BACKUP_RETENTION_DAYS должен быть положительным целым числом."

for command_name in pg_dump pg_restore psql sha256sum df find mktemp mountpoint tr awk; do
  command -v "$command_name" >/dev/null 2>&1 || fail "Не найдена команда $command_name."
done

[[ -d "$BACKUP_DIR" ]] || fail "Каталог BACKUP_DIR не существует: $BACKUP_DIR. Сначала подключи отдельное хранилище."

BACKUP_DIR_REAL="$(cd -- "$BACKUP_DIR" && pwd -P)"
case "$BACKUP_DIR_REAL/" in
  "$REPO_ROOT/"*) fail "Резервные копии нельзя хранить внутри репозитория." ;;
esac

if [[ "${BACKUP_ALLOW_LOCAL_DIR:-false}" != "true" ]]; then
  mountpoint -q -- "$BACKUP_DIR_REAL" || fail "BACKUP_DIR не является точкой монтирования. Не записываю архив на локальный диск сервера."
fi

export PGHOST="$DB_HOST"
export PGPORT="$DB_PORT"
export PGDATABASE="$DB_NAME"
export PGUSER="$DB_USER"
export PGPASSWORD="$DB_PASSWORD"
export PGSSLMODE="${DB_SSLMODE:-prefer}"
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"

pg_dump_version="$(pg_dump --version | awk '{print $3}')"
pg_dump_major="${pg_dump_version%%.*}"
server_version="$(psql -X -w -qAt -d postgres -c 'SHOW server_version')"
server_major="${server_version%%.*}"

[[ "$pg_dump_major" =~ ^[0-9]+$ && "$server_major" =~ ^[0-9]+$ ]] || fail "Не удалось определить версии PostgreSQL."
(( pg_dump_major >= server_major )) || fail "pg_dump версии $pg_dump_version старее сервера PostgreSQL $server_version."

database_size_bytes="$(psql -X -w -qAt -d "$DB_NAME" -c 'SELECT pg_database_size(current_database())')"
[[ "$database_size_bytes" =~ ^[0-9]+$ ]] || fail "Не удалось определить размер базы."
required_kb=$(( (database_size_bytes + database_size_bytes / 5 + 1023) / 1024 ))
available_kb="$(df -Pk "$BACKUP_DIR_REAL" | awk 'NR == 2 {print $4}')"
[[ "$available_kb" =~ ^[0-9]+$ ]] || fail "Не удалось определить свободное место в хранилище."
(( available_kb >= required_kb )) || fail "Недостаточно места: свободно $available_kb KiB, требуется примерно $required_kb KiB с запасом."

stamp="$(date -u '+%Y%m%dT%H%M%SZ')"
safe_db_name="$(printf '%s' "$DB_NAME" | tr -c 'A-Za-z0-9_-' '_')"
base_name="postgres-${safe_db_name}-${stamp}-$$.dump"
backup_file="$BACKUP_DIR_REAL/$base_name"
tmp_file=""
tmp_checksum=""
tmp_meta=""

cleanup() {
  [[ -z "$tmp_file" ]] || rm -f -- "$tmp_file"
  [[ -z "$tmp_checksum" ]] || rm -f -- "$tmp_checksum"
  [[ -z "$tmp_meta" ]] || rm -f -- "$tmp_meta"
}
trap cleanup EXIT
trap on_error ERR

log "Начато резервное копирование базы $DB_NAME; PostgreSQL $server_version; pg_dump $pg_dump_version."

tmp_file="$(mktemp "$BACKUP_DIR_REAL/.${base_name}.tmp.XXXXXX")"
pg_dump --format=custom --no-owner --no-acl --file="$tmp_file" --dbname="$DB_NAME"

[[ -s "$tmp_file" ]] || fail "pg_dump создал пустой файл."
pg_restore --list "$tmp_file" >/dev/null
mv -- "$tmp_file" "$backup_file"
tmp_file=""

tmp_checksum="$(mktemp "$BACKUP_DIR_REAL/.${base_name}.sha256.XXXXXX")"
sha256sum "$backup_file" > "$tmp_checksum"
mv -- "$tmp_checksum" "$backup_file.sha256"
tmp_checksum=""

tmp_meta="$(mktemp "$BACKUP_DIR_REAL/.${base_name}.meta.XXXXXX")"
{
  printf 'created_at_utc=%s\n' "$stamp"
  printf 'database=%s\n' "$DB_NAME"
  printf 'postgres_server_version=%s\n' "$server_version"
  printf 'pg_dump_version=%s\n' "$pg_dump_version"
  printf 'format=custom\n'
} > "$tmp_meta"
mv -- "$tmp_meta" "$backup_file.meta"
tmp_meta=""

# Старые архивы удаляются только после создания, проверки и контрольной суммы новой копии.
while IFS= read -r -d '' old_file; do
  rm -f -- "$old_file" "$old_file.sha256" "$old_file.meta"
done < <(find "$BACKUP_DIR_REAL" -maxdepth 1 -type f \
  -name "postgres-${safe_db_name}-*.dump" -mtime "+$((BACKUP_RETENTION_DAYS - 1))" -print0)

log "Резервная копия создана и проверена: $base_name."
log "Хранение: ${BACKUP_RETENTION_DAYS} дней. Содержимое базы и пароль в журнал не выводились."
