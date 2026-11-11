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
  log "ERROR: восстановление завершилось с кодом ${status}. Тестовая база могла остаться частично заполненной; не используй её как рабочую."
  exit "$status"
}

if [[ -z "${ENV_FILE:-}" ]]; then
  fail "Укажи ENV_FILE с реквизитами отдельного тестового PostgreSQL. Не используй настройки рабочей базы."
fi

[[ $# -eq 1 ]] || fail "Использование: ENV_FILE=.env.backup-test RESTORE_TEST_DB=имя_restore_test RESTORE_CONFIRM_TARGET=имя_restore_test $0 /путь/к/копии.dump"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ENV_FILE="$(cd -- "$(dirname -- "$ENV_FILE")" && pwd -P)/$(basename -- "$ENV_FILE")"
[[ -f "$ENV_FILE" ]] || fail "Не найден файл настроек: $ENV_FILE"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${DB_HOST:?В ENV_FILE не задан DB_HOST}"
: "${DB_PORT:=5432}"
: "${DB_NAME:?В ENV_FILE не задан DB_NAME}"
: "${DB_USER:?В ENV_FILE не задан DB_USER}"
: "${DB_PASSWORD:?В ENV_FILE не задан DB_PASSWORD}"

[[ "$DB_NAME" == *_backup_fixture ]] || fail "Источник восстановления должен быть отдельной учебной базой с именем, оканчивающимся на _backup_fixture."
BACKUP_FILE="$1"
[[ -f "$BACKUP_FILE" && -s "$BACKUP_FILE" ]] || fail "Файл резервной копии не найден или пуст."
[[ -f "$BACKUP_FILE.sha256" ]] || fail "Нет файла контрольной суммы $BACKUP_FILE.sha256."
[[ "${RESTORE_TEST_DB:-}" =~ ^[A-Za-z0-9_-]+_restore_test$ ]] || fail "RESTORE_TEST_DB должен оканчиваться на _restore_test."
[[ "$RESTORE_TEST_DB" != "$DB_NAME" ]] || fail "Нельзя восстанавливать базу поверх исходной."
[[ "${RESTORE_CONFIRM_TARGET:-}" == "$RESTORE_TEST_DB" ]] || fail "Для подтверждения укажи RESTORE_CONFIRM_TARGET с точным именем тестовой базы."

for command_name in pg_restore psql createdb sha256sum; do
  command -v "$command_name" >/dev/null 2>&1 || fail "Не найдена команда $command_name."
done

export PGHOST="$DB_HOST"
export PGPORT="$DB_PORT"
export PGUSER="$DB_USER"
export PGPASSWORD="$DB_PASSWORD"
export PGSSLMODE="${DB_SSLMODE:-prefer}"
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"

log "Проверяю контрольную сумму файла."
sha256sum --check "$BACKUP_FILE.sha256" >/dev/null
pg_restore --list "$BACKUP_FILE" >/dev/null

database_exists="$(psql -X -w -qAt -d postgres -c "SELECT 1 FROM pg_database WHERE datname = '$RESTORE_TEST_DB'")"
[[ -z "$database_exists" ]] || fail "База $RESTORE_TEST_DB уже существует. Скрипт не очищает и не перезаписывает базы."

log "Создаю новую пустую тестовую базу $RESTORE_TEST_DB."
createdb --maintenance-db=postgres --owner="$DB_USER" "$RESTORE_TEST_DB"

log "Восстанавливаю архив в отдельную тестовую базу."
pg_restore --exit-on-error --no-owner --no-acl --dbname="$RESTORE_TEST_DB" "$BACKUP_FILE"

table_count="$(psql -X -w -qAt -d "$RESTORE_TEST_DB" -c "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")"
[[ "$table_count" =~ ^[0-9]+$ ]] && (( table_count > 0 )) || fail "В восстановленной базе не найдены таблицы приложения."

log "Восстановление завершено. База: $RESTORE_TEST_DB; таблиц в public: $table_count."
log "Проверь связи пользователя, проекта и задачи через Django по инструкции infra/backup.md."
log "Исходная и рабочая базы не изменялись. Скрипт ничего не удаляет."
