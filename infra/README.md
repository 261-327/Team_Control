# PostgreSQL для локальной разработки

Инструкция поднимает PostgreSQL через корневой `compose.yaml`. В нём также есть сервисы Django, frontend и локального ИИ, но для проверки только базы запускаем сервис `db`.

## Требования

- Установленный и запущенный Docker Desktop (Windows) или Docker Engine.
- Docker Compose v2: команда `docker compose version` должна выполняться без ошибки.
- Репозиторий `Team_Control`, терминал открыт в его корне.

## 1. Создать локальный файл настроек

В PowerShell из корня репозитория:

```powershell
if (-not (Test-Path "infra\.env")) {
    Copy-Item "infra\.env.example" "infra\.env"
}
```

В Bash (Linux/macOS/WSL):

```sh
if [ ! -f infra/.env ]; then cp infra/.env.example infra/.env; fi
```

`infra/.env.example` — шаблон для команды; `infra/.env` — локальные настройки твоего компьютера. В примере используются учебные значения для локальной разработки. Не используй примерный пароль на публичном сервере. Не коммить и не отправляй файл `infra/.env`.

Если стандартный host-порт `5432` занят или зарезервирован Windows, измени только `DB_PORT` в своём `infra/.env`, например, на `15432`. Не меняй внутренний порт PostgreSQL `5432`.

## 2. Проверить конфигурацию и запустить только базу

Все команды ниже выполняются из корня репозитория:

```powershell
docker compose --env-file infra/.env config --quiet
docker compose --env-file infra/.env up -d db
docker compose --env-file infra/.env ps
```

У сервиса `db` дождись статуса `healthy`. Проверить готовность PostgreSQL можно так:

```powershell
docker compose --env-file infra/.env exec db pg_isready -U postgres_user -d team_control_db
```

Ожидается сообщение, что сервер принимает подключения. Если healthcheck не проходит, посмотри журнал:

```powershell
docker compose --env-file infra/.env logs --tail 100 db
```

## 3. Адрес подключения зависит от того, где запущен Django

- Django, запущенный прямо на компьютере, подключается к `127.0.0.1` и порту `DB_PORT` из локального `infra/.env` (по умолчанию `5432`; на компьютере с занятым портом это может быть, например, `15432`).
- Django-контейнер в том же Compose-проекте подключается к хосту `db` и внутреннему порту `5432`. В контейнере `127.0.0.1` означает сам контейнер, а не PostgreSQL.
- Порт базы публикуется только на `127.0.0.1` хоста, а не на всех сетевых интерфейсах.

Корневой Compose передаёт Django-контейнеру `DB_HOST=db` и `DB_PORT=5432`; внешний `DB_PORT` применяется только к порту на компьютере. Имена базы, пользователь и пароль берутся из `infra/.env` и должны совпадать у сервиса PostgreSQL и Django.

## 4. Проверить сохранность данных

Данные хранятся в именованном Docker volume `postgres_data`, а не в папке `infra`. Для проверки используй только локальную учебную базу. Подключись к PostgreSQL:

```powershell
docker compose --env-file infra/.env exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

В приглашении `psql` выполни тестовые SQL-команды:

```sql
CREATE TABLE IF NOT EXISTS infra_volume_check (
    id integer PRIMARY KEY,
    note text NOT NULL
);
INSERT INTO infra_volume_check (id, note)
VALUES (1, 'volume-ok')
ON CONFLICT (id) DO UPDATE SET note = EXCLUDED.note;
SELECT * FROM infra_volume_check;
```

Проверь, что результат содержит `volume-ok`, затем выйди командой `\\q`.

Останови и снова запусти контейнеры:

```powershell
docker compose --env-file infra/.env down
docker compose --env-file infra/.env up -d db
docker compose --env-file infra/.env ps
```

После перехода `db` в статус `healthy` снова подключись командой выше и выполни:

```sql
SELECT * FROM infra_volume_check;
```

Запись `volume-ok` должна остаться. Не используй `docker compose down -v` для проверки: параметр `-v` удаляет именованные тома и данные в них.

## 5. Запуск всего приложения

Инструкция запуска полного стека находится в корневом `README.md`. Перед запуском Django проверь с backend-командой, что готова и согласована модель пользователя. Запуск сервиса `db` отдельно не применяет миграции; не запускай первые миграции до такого согласования. После готовности backend вместе с ответственными примени миграции и проверь `/api/health/`.

## Секреты

Настоящий `infra/.env` должен быть исключён из Git. В PR добавляй только пример `infra/.env.example`, команды проверки и результаты без паролей или содержимого локального `.env`.

## Автоматические проверки backend (GitHub Actions)

Проверки выполняются workflow `.github/workflows/backend-membership.yml`.

Workflow запускается при:
- создании или обновлении Pull Request с изменениями в `backend/`;
- отправке изменений в `main`.

### Где смотреть результат

1. Открой репозиторий Team_Control на GitHub.
2. Перейди во вкладку **Actions**.
3. Выбери **Backend membership checks**.
4. Открой нужный запуск и выбери задачу `django-postgres`.
5. Найди шаг, завершившийся ошибкой, и открой его логи.

### Что означают ошибки

- `pip install` — проблема с установкой Python-зависимостей.
- `manage.py check` — ошибка конфигурации Django.
- `makemigrations --check --dry-run` — отсутствуют необходимые миграции.
- `migrate` — ошибка применения миграций к тестовой базе.
- `manage.py test` — не прошли автоматические тесты.

В workflow используется временная PostgreSQL 15 и тестовые настройки почты. Рабочая база, реальные пользователи и SMTP не используются.

После исправления ошибки отправь новый коммит в свою ветку: GitHub автоматически повторит проверку.
