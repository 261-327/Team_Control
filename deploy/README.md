# Запуск на сервере команды

Этот запуск использует **существующую базу Django с аккаунтами ребят**. Локальная `backend/local.sqlite3` нужна только для разработки и на сервер не переносится.

Нужны Docker Engine, Docker Compose и настроенный HTTPS-домен. Контейнеры запускают Django через Gunicorn, собранный Next.js и внутренний Nginx. PostgreSQL можно оставить там, где он уже работает.

## 1. Настройки

Из корня обновлённого репозитория:

```sh
cp .env.server.example .env.server
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
```

В `.env.server` заполни:

- `FRONTEND_URL` — полный адрес сайта, например `https://sipi.university.ru`.
- `DJANGO_ALLOWED_HOSTS` — домен без протокола, например `sipi.university.ru`.
- `CSRF_TRUSTED_ORIGINS` — тот же полный адрес с `https://`. Несколько адресов разделяются запятыми.
- `DJANGO_SECRET_KEY` — сгенерированное значение. Сохрани его при последующих перезапусках.
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE` — реквизиты **той же базы**, которую использует текущий Django. Для PostgreSQL вне Docker укажи доступный из контейнера адрес; `localhost` внутри контейнера означает сам контейнер.
- `EMAIL_*`, `DEFAULT_FROM_EMAIL` — действующие SMTP-настройки. На сервере коды входа отправляются письмом, console-backend не используется.

Файл с заполненными значениями игнорируется Git. Не отправляй его в репозиторий или чат.

## 2. Выбери способ подключения базы

Перед обновлением сделай обычную резервную копию существующей базы. Миграции применяются автоматически; сброс базы и `flush` не нужны.

### PostgreSQL уже работает отдельно

В `DB_HOST` укажи его адрес. Запускаются только приложение и шлюз:

```sh
docker compose --env-file .env.server -f compose.server.yaml config --quiet
docker compose --env-file .env.server -f compose.server.yaml up -d --build --wait
```

### PostgreSQL был запущен прежним Docker Compose этого проекта

Сохрани прежние `DB_NAME`, `DB_USER`, `DB_PASSWORD`. Укажи `DB_HOST=db`, а в `POSTGRES_VOLUME` — точное имя прежнего тома. При стандартном запуске проекта это `backend_postgres_data`. Уточнить имена томов можно командой `docker volume ls`.

```sh
docker volume inspect backend_postgres_data
# Если том называется иначе, используй его имя в команде и в POSTGRES_VOLUME.
docker compose --env-file .env.server -f compose.server.yaml -f compose.server-db.yaml config --quiet
docker compose --env-file .env.server -f compose.server.yaml -f compose.server-db.yaml up -d --build --wait
```

Том объявлен внешним: если указанного тома нет, запуск остановится, вместо того чтобы незаметно создать пустую базу. Не выполняй `docker compose down -v` при обновлении. Для действительно нового проекта без существующих аккаунтов создание пустого тома должно быть отдельным осознанным действием.

При смене старого Compose на серверный останови старые backend/frontend-контейнеры, если они ещё обслуживают сайт; сам PostgreSQL и его том не удаляй. Имя Compose-проекта сохранено — `backend`.

## 3. Подключи HTTPS-домен

Приложение слушает `127.0.0.1:8080` на сервере. В существующий HTTPS `server`-блок внешнего Nginx добавь `location` из [host-nginx.conf.example](host-nginx.conf.example). Он передаёт исходный Host и протокол запроса.

Проверь конфигурацию внешнего Nginx штатной командой `nginx -t`, затем перезагрузи её. TLS-сертификат обслуживает внешний сервер, а не контейнер приложения. Не открывай внутренние Django/Next.js-порты наружу.

На одном домене будут доступны:

- `/` — интерфейс Сипи;
- `/api/health/` — готовность приложения и базы;
- `/api/` — Django API;
- `/admin/` — админка Django со статическими файлами;
- `/legacy/` — прежние Django-страницы для совместимости.

Если сегодня проверяете запуск по обычному HTTP и IP, укажи `http://IP:порт` в `FRONTEND_URL` и `CSRF_TRUSTED_ORIGINS`, IP без порта в `DJANGO_ALLOWED_HOSTS`, `COOKIE_SECURE=false` и нужный адрес в `SIPI_BIND_ADDRESS`. Для общего HTTPS-сервера оставь шлюз на loopback и `COOKIE_SECURE=true`.

## 4. Проверь результат

Используй тот же набор `-f`, с которым запускалось приложение:

```sh
docker compose --env-file .env.server -f compose.server.yaml ps
docker compose --env-file .env.server -f compose.server.yaml logs --tail=100 backend frontend gateway
```

Открой публичный домен, войди **существующим** аккаунтом Django, получи код по почте и проверь проекты. Создай задачу, перенеси её на доске и обнови страницу. Если прежнего аккаунта нет, проверь подключённую базу и том; создавать замену аккаунту для решения этой проблемы не нужно.

Изменения API и UI должны быть из одной версии репозитория. `DJANGO_API_URL` — внутренний адрес Django для серверного прокси Next.js; в Docker он уже задан как `http://backend:8000`. Браузер использует единый публичный домен.

## Повторное обновление

После получения новых изменений повтори свою команду `up -d --build --wait`. Миграции и сбор статических файлов входят в запуск backend-контейнера. Тестовые данные не добавляются. Текущая база и её том сохраняются.
