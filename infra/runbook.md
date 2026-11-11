# Runbook: диагностика и резервное восстановление Team Control

Этот документ предназначен для дежурного участника команды. Команды выполняются на Linux-сервере из каталога репозитория. Перед восстановлением или удалением данных согласуй действия с ответственным за сервер и базу.

Контакты:
- Ответственный за сервер: **указать имя и контакт команды**.
- Ответственный за PostgreSQL и резервные копии: **указать имя и контакт команды**.
- Последняя успешная проверка восстановления: **заполнить фактическую дату и время**.
- Следующая ручная проверка восстановления: **указать дату**.

## Персональные данные и резервные копии

До отправки production dump в Cloudflare R2 убедись, что владелец проекта подтвердил допустимость такого размещения с учётом локализации и трансграничной передачи персональных данных. До подтверждения используй только вымышленные тестовые данные. Не загружай production dump с персональными данными граждан РФ во внешнее хранилище за пределами РФ без отдельной правовой проверки.

## 1. Сайт не открывается

1. Проверь доступность health endpoint с самого сервера:

~~~sh
curl -fsS https://<домен>/api/health/
~~~

2. Проверь состояние контейнеров:

~~~sh
docker compose --env-file .env.server -f compose.server.yaml ps
~~~

Если PostgreSQL подключён дополнительным файлом Compose, добавь -f compose.server-db.yaml.

3. Посмотри последние 100 строк логов без вывода полного окружения:

~~~sh
docker compose --env-file .env.server -f compose.server.yaml logs --tail=100 backend frontend gateway
~~~

4. Если контейнер остановлен, сначала изучи ошибку. После исправления причины допустим перезапуск только затронутого сервиса:

~~~sh
docker compose --env-file .env.server -f compose.server.yaml restart backend
~~~

Проверь внешний Nginx и HTTPS-сертификат отдельно. Не запускай docker compose down -v, не удаляй volumes и не пересоздавай базу ради устранения ошибки сайта.

## 2. PostgreSQL недоступен

1. Загрузи переменные в защищённой shell-сессии, не выводя их на экран:

~~~sh
set -a
. ./.env.server
set +a
~~~

2. Проверь PostgreSQL в зависимости от режима:

~~~sh
if [ "$BACKUP_DB_MODE" = "docker" ]; then
  docker compose --env-file .env.server -f compose.server.yaml -f compose.server-db.yaml exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME"
else
  PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -U "$DB_USER"
fi
~~~

3. Если используется база из compose.server-db.yaml, проверь её состояние и последние сообщения:

~~~sh
docker compose --env-file .env.server -f compose.server.yaml -f compose.server-db.yaml ps db
docker compose --env-file .env.server -f compose.server.yaml -f compose.server-db.yaml logs --tail=100 db
~~~

4. Проверь адрес, порт, имя БД, права пользователя и доступность сетевого маршрута. Не печатай .env.server целиком и не отправляй пароль в чат или issue.

Не запускай миграции вручную, flush, удаление volume или восстановление поверх рабочей базы без отдельного согласованного плана.

## 3. Закончилось место на диске

1. Проверь свободное место и Docker:

~~~sh
df -h
docker system df
~~~

Резервная копия PostgreSQL отправляется напрямую в Cloudflare R2, полный архив на локальном диске приложения не создаётся. Проверь использование bucket и наличие свежих объектов в приватном R2 через Cloudflare Dashboard или rclone с отдельным bucket-scoped ключом.

Не запускай docker system prune --volumes, docker volume prune и не удаляй PostgreSQL/media volumes. Не удаляй последнюю успешную резервную копию. Старые архивы автоматически удаляются только после успешной загрузки и проверки новой копии.

## 4. Резервная копия не создалась

1. Проверь статус и журнал systemd:

~~~sh
sudo systemctl status team-control-backup.service --no-pager
sudo journalctl -u team-control-backup.service -n 100 --no-pager
sudo systemctl list-timers team-control-backup.timer
~~~

2. Проверь версию rclone и PostgreSQL:

~~~sh
set -a
. ./.env.server
set +a
rclone version
if [ "$BACKUP_DB_MODE" = "docker" ]; then
  docker compose --env-file .env.server -f compose.server.yaml -f compose.server-db.yaml exec -T db pg_dump --version
  docker compose --env-file .env.server -f compose.server.yaml -f compose.server-db.yaml exec -T db psql -X -w -qAt -U "$DB_USER" -d postgres -c 'SHOW server_version'
else
  pg_dump --version
  psql -X -w -qAt -d postgres -c 'SHOW server_version'
fi
~~~

Проверь Account ID, bucket, bucket-scoped API key, разрешения Object Read & Write и сетевой доступ к R2. Не выводи и не копируй Secret Access Key в логи или issue.

3. Исправь первопричину и запусти сервис вручную:

~~~sh
sudo systemctl start team-control-backup.service
sudo systemctl status team-control-backup.service --no-pager
~~~

4. Убедись, что в приватном R2 bucket появились три объекта: .dump, .dump.sha256 и .dump.meta. Проверь checksum и пробное восстановление командами из backup.md.

Не отмечай запуск успешным по одному наличию файла. Не удаляй старые копии, если новый архив не прошёл проверку.

## Восстановление данных

restore-test.sh предназначен только для отдельного тестового PostgreSQL: исходная учебная база должна иметь суффикс `_backup_fixture` и таблицу `backup_test_fixture` с меткой `team-control-backup-test-only`; перед запуском требуется явное подтверждение изолированного тестового сервера и имени целевой базы с суффиксом `_restore_test`. Скрипт не перезаписывает существующие базы и не удаляет их при ошибке.

Восстановление production — отдельная аварийная операция. До неё:
1. останови изменения приложения согласованным способом;
2. свяжись с ответственным за PostgreSQL и руководителем команды;
3. зафиксируй время последней успешной копии и ожидаемую потерю изменений после неё;
4. согласуй целевую базу, окно восстановления и план возврата;
5. сначала проверь архив и тестовое восстановление; не используй тестовый скрипт для рабочей базы.

После аварии проверь вход, проекты, участников, задачи, их статусы и вложения. Зафиксируй причину, время обнаружения, выбранную копию, фактическое время восстановления и результат проверки.

## Как часто проверять

После настройки и включения systemd timer backup запускается ежедневно. Ответственный проверяет журнал после каждого неудачного запуска и проводит ручное пробное восстановление не реже одного раза в месяц, а также после существенных изменений схемы или версии PostgreSQL.
