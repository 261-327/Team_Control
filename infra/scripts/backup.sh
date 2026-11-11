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
  log "ERROR: резервное копирование завершилось с кодом \${status}."
  exit "$status"
}

SCRIPT_DIR="$(cd -- "$(dirname -- "\${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
ENV_FILE="\${ENV_FILE:-$REPO_ROOT/.env.server}"

[[ -f "$ENV_FILE" ]] || fail "Не найден файл настроек: $ENV_FILE"

# .env.server должен содержать обычные shell-совместимые KEY=value.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "\${DB_HOST:?В ENV_FILE не задан DB_HOST}"
: "\${DB_PORT:=5432}"
: "\${DB_NAME:?В ENV_FILE не задан DB_NAME}"
: "\${DB_USER:?В ENV_FILE не задан DB_USER}"
: "\${DB_PASSWORD:?В ENV_FILE не задан DB_PASSWORD}"
: "\${R2_ACCOUNT_ID:?В ENV_FILE не задан R2_ACCOUNT_ID}"
: "\${R2_ACCESS_KEY_ID:?В ENV_FILE не задан R2_ACCESS_KEY_ID}"
: "\${R2_SECRET_ACCESS_KEY:?В ENV_FILE не задан R2_SECRET_ACCESS_KEY}"
: "\${R2_BUCKET:?В ENV_FILE не задан R2_BUCKET}"

BACKUP_RETENTION_DAYS="\${BACKUP_RETENTION_DAYS:-7}"
R2_PREFIX="\${R2_PREFIX:-team-control/postgres}"

[[ "$DB_NAME" =~ ^[A-Za-z0-9_-]+$ ]] || fail "DB_NAME содержит неподдерживаемые символы."
[[ "$R2_BUCKET" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] || fail "Проверь имя R2_BUCKET."
[[ "$R2_PREFIX" =~ ^[A-Za-z0-9/_-]+$ ]] || fail "R2_PREFIX может содержать только латинские буквы, цифры, /, _ и -."
[[ "$BACKUP_RETENTION_DAYS" =~ ^[1-9][0-9]*$ ]] || fail "BACKUP_RETENTION_DAYS должен быть положительным целым числом."

for command_name in pg_dump pg_restore psql sha256sum rclone awk tr; do
  command -v "$command_name" >/dev/null 2>&1 || fail "Не найдена команда $command_name."
done

rclone_version="$(rclone version | awk 'NR == 1 {sub(/^rclone v/, ""); print $1}')"
[[ "$rclone_version" =~ ^([0-9]+)\.([0-9]+) ]] || fail "Не удалось определить версию rclone."
rclone_major="\${BASH_REMATCH[1]}"
rclone_minor="\${BASH_REMATCH[2]}"
(( rclone_major > 1 || (rclone_major == 1 && rclone_minor >= 59) )) || fail "Нужен rclone версии 1.59 или новее."

# Конфигурация R2 задаётся через окружение; ключи не сохраняются в rclone.conf.
export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
export RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export RCLONE_CONFIG_R2_ENDPOINT="https://\${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
export RCLONE_CONFIG_R2_REGION=auto
export RCLONE_CONFIG_R2_ACL=private
export RCLONE_CONFIG_R2_NO_CHECK_BUCKET=true

export PGHOST="$DB_HOST"
export PGPORT="$DB_PORT"
export PGDATABASE="$DB_NAME"
export PGUSER="$DB_USER"
export PGPASSWORD="$DB_PASSWORD"
export PGSSLMODE="\${DB_SSLMODE:-prefer}"
export PGCONNECT_TIMEOUT="\${PGCONNECT_TIMEOUT:-10}"

pg_dump_version="$(pg_dump --version | awk '{print $3}')"
pg_dump_major="\${pg_dump_version%%.*}"
server_version="$(psql -X -w -qAt -d postgres -c 'SHOW server_version')"
server_major="\${server_version%%.*}"

[[ "$pg_dump_major" =~ ^[0-9]+$ && "$server_major" =~ ^[0-9]+$ ]] || fail "Не удалось определить версии PostgreSQL."
(( pg_dump_major >= server_major )) || fail "pg_dump версии $pg_dump_version старее сервера PostgreSQL $server_version."

stamp="$(date -u '+%Y%m%dT%H%M%SZ')"
safe_db_name="$(printf '%s' "$DB_NAME" | tr -c 'A-Za-z0-9_-' '_')"
base_name="postgres-\${safe_db_name}-\${stamp}-$$.dump"
remote_dir="R2:$R2_BUCKET/\${R2_PREFIX%/}/$DB_NAME"
remote_file="$remote_dir/$base_name"

trap on_error ERR

log "Проверяю подключение к Cloudflare R2 и PostgreSQL."
rclone mkdir "$remote_dir"
rclone lsf "$remote_dir" >/dev/null
log "Создаю custom dump и отправляю поток напрямую в R2. Локальный файл базы не создаётся."

# Буферы ограничены: один multipart chunk 8 MiB, одна параллельная загрузка.
pg_dump --format=custom --no-owner --no-acl --dbname="$DB_NAME" |
  rclone --buffer-size 0 --transfers 1 --s3-upload-concurrency 1 \
    --s3-chunk-size 8M --streaming-upload-cutoff 1M \
    rcat "$remote_file"

remote_listing="$(rclone ls "$remote_dir")"
remote_size="$(awk -v target="$base_name" '$2 == target {print $1; exit}' <<< "$remote_listing")"
[[ "$remote_size" =~ ^[0-9]+$ ]] && (( remote_size > 0 )) || fail "Объект в R2 отсутствует или пуст."

# Читаем объект обратно потоком, без сохранения на диск, проверяем архив и checksum.
rclone --buffer-size 0 cat "$remote_file" | pg_restore --list - >/dev/null
remote_hash="$(rclone --buffer-size 0 cat "$remote_file" | sha256sum | awk '{print $1}')"
[[ "$remote_hash" =~ ^[a-f0-9]{64}$ ]] || fail "Не удалось вычислить SHA-256 загруженного объекта."

printf '%s  %s\n' "$remote_hash" "$base_name" |
  rclone --buffer-size 0 rcat "$remote_file.sha256"

metadata="$(mktemp)"
trap 'rm -f -- "$metadata"' EXIT
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
trap on_error ERR

# Убеждаемся, что все три объекта видны в R2 до ротации старых копий.
uploaded_objects="$(rclone lsf "$remote_dir" --files-only)"
grep -Fxq "$base_name" <<< "$uploaded_objects" || fail "Не найден архив в R2 после загрузки."
grep -Fxq "$base_name.sha256" <<< "$uploaded_objects" || fail "Не найдена SHA-256 контрольная сумма в R2."
grep -Fxq "$base_name.meta" <<< "$uploaded_objects" || fail "Не найданы метаданные копии в R2."

# Ротация запускается только после загрузки и проверки нового архива и sidecar-файлов.
rclone delete --min-age "\${BACKUP_RETENTION_DAYS}d" "$remote_dir"

log "Резервная копия загружена и проверена в R2: $base_name ($remote_size bytes)."
log "Хранение: \${BACKUP_RETENTION_DAYS} дней. Полный архив на локальный диск не записывался."
