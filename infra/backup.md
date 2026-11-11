# Резервное копирование PostgreSQL в Cloudflare R2

## Архитектура

Резервная копия PostgreSQL отправляется потоком из pg_dump в Cloudflare R2 через S3 API с помощью rclone. Полный архив не создаётся на системном диске приложения. После загрузки скрипт читает объект из R2 потоком, вычисляет SHA-256, сохраняет контрольную сумму и метаданные.

Используется отдельный закрытый R2 bucket, предназначенный только для резервных копий. Не смешивай backup с пользовательскими материалами проекта и не используй для него тот же ключ, что у Django.

Файлы:
- infra/scripts/backup.sh — потоковый backup и очистка архивов старше срока хранения.
- infra/scripts/restore-test.sh — восстановление локально скачанного дампа только в новую тестовую БД.
- infra/runbook.md — диагностика типичных сбоев.

## 1. Подготовить Cloudflare R2

В Cloudflare Dashboard:

1. Открой R2 Object Storage и создай отдельный приватный bucket, например team-control-backups. Не включай публичный доступ.
2. В Manage R2 API Tokens создай ключ с разрешением Object Read & Write и ограничь его только этим bucket. Не используй глобальный ключ аккаунта.
3. Сохрани Access Key ID и Secret Access Key в защищённом окружении сервера. Secret Access Key показывается при создании; его нельзя публиковать в Git, issue, PR, переписке или логах.
4. Возьми Account ID из S3 API endpoint вида https://<ACCOUNT_ID>.r2.cloudflarestorage.com.

Для восстановления на отдельной тестовой машине понадобится доступ на чтение этого же bucket. Используй тот же ключ только в приватном локальном файле, не добавляй его в репозиторий.

Официальная инструкция: https://developers.cloudflare.com/r2/examples/rclone/. Нужен rclone версии 1.59 или новее.

## 2. Настройки сервера

В защищённый .env.server добавь параметры:

~~~dotenv
# Режим подключения к PostgreSQL:
# host — сервер может подключиться к DB_HOST напрямую;
# docker — PostgreSQL запущен сервисом db из compose.server-db.yaml.
BACKUP_DB_MODE=docker

R2_ACCOUNT_ID=<account-id>
R2_BUCKET=team-control-backups
R2_ACCESS_KEY_ID=<access-key-id>
R2_SECRET_ACCESS_KEY=<secret-access-key>
R2_PREFIX=team-control/postgres
BACKUP_RETENTION_DAYS=7
~~~

Не коммить заполненный .env.server. В репозитории есть только шаблон .env.server.example.

Режим PostgreSQL:
- BACKUP_DB_MODE=host: установлены pg_dump и psql на сервере, а адрес DB_HOST доступен из host-системы.
- BACKUP_DB_MODE=docker: PostgreSQL работает в Compose-сервисе db и подключён через compose.server-db.yaml. Запускай скрипт из каталога репозитория; Docker Compose должен иметь доступ к существующему контейнеру и его внешнему volume.

Скрипт использует текущие DB_NAME и DB_USER. Для режима host также нужны DB_HOST, DB_PASSWORD и DB_PORT. В режиме docker команды pg_dump и psql выполняются внутри контейнера БД; сам дамп передаётся из контейнера напрямую в rclone.

## 3. Проверить доступ к R2

Установи rclone версии 1.59 или новее. Скрипт создаёт временную конфигурацию remote R2 через переменные окружения; ключи не записываются в rclone.conf.

После заполнения .env.server из корня репозитория запусти:

~~~sh
ENV_FILE=/opt/team-control/.env.server bash ./infra/scripts/backup.sh
~~~

Путь /opt/team-control замени на реальный путь репозитория на сервере.

Первая проверка одновременно проверит подключение к БД, доступ к bucket, загрузит дамп, скачает поток для вычисления SHA-256, сохранит checksum/metadata и покажет итог. Полный архив на локальный диск сервера не записывается.

Параметры передачи ограничены: один upload transfer, один multipart chunk 8 MiB. Это снижает потребление памяти rclone. Потоковую загрузку нельзя автоматически повторить с середины, если соединение оборвалось: неудачный запуск должен завершиться ошибкой, следующий запуск создаст новый архив с новым именем.

Путь объектов:
R2:<bucket>/<prefix>/<DB_NAME>/postgres-<DB_NAME>-<UTC timestamp>-<pid>.dump

Для каждого архива рядом хранятся:
- .dump.sha256 — SHA-256 полного объекта;
- .dump.meta — время UTC, имя базы, версии PostgreSQL/rclone, размер и SHA-256.

Срок хранения по умолчанию — семь дней. Удаление старых объектов выполняется только после успешной загрузки и проверки новой копии и ограничено каталогом конкретной базы.

## 4. Пробное восстановление — только отдельно от сервера приложения

Восстановление проверь на отдельной тестовой машине или отдельном тестовом PostgreSQL, который не подключён к рабочей базе. Не используй production .env.server.

Создай локальный файл .env.backup-test вне Git. Укажи в нём параметры отдельной тестовой БД, суффикс базы _backup_fixture и R2-параметры с доступом к bucket:

~~~dotenv
BACKUP_DB_MODE=host
DB_HOST=127.0.0.1
DB_PORT=55432
DB_NAME=team_control_backup_fixture
DB_USER=postgres_user
DB_PASSWORD=<пароль отдельной тестовой БД>
DB_SSLMODE=prefer

R2_ACCOUNT_ID=<account-id>
R2_BUCKET=team-control-backups
R2_ACCESS_KEY_ID=<bucket-scoped-access-key>
R2_SECRET_ACCESS_KEY=<bucket-scoped-secret>
R2_PREFIX=team-control/postgres
BACKUP_RETENTION_DAYS=7
~~~

Порт 55432 здесь — пример порта отдельного тестового PostgreSQL. Не направляй этот файл на производственную базу.

Загрузи значения из тестового файла и создай тестовую базу с миграциями Django:

~~~sh
set -a
. ./.env.backup-test
set +a

PGPASSWORD="$DB_PASSWORD" createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
python backend/manage.py migrate --noinput
~~~

Добавь обязательную тестовую метку, которую проверяет скрипт восстановления:

~~~sh
PGPASSWORD="$DB_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE TABLE public.backup_test_fixture (marker text PRIMARY KEY); INSERT INTO public.backup_test_fixture(marker) VALUES ('team-control-backup-test-only');"
~~~

Создай связанные вымышленные данные:

~~~sh
python backend/manage.py shell -c '
from tasks.models import WorkspaceUser, Project, Membership, Board, Column, Task
user = WorkspaceUser.objects.create_user(username="backup-smoke-user", email="backup-smoke@example.invalid", password="temporary-test-only")
project = Project.objects.create(name="Backup restore fixture", owner=user)
Membership.objects.create(user=user, project=project, role="developer", developer_specialization="backend", is_confirmed=True)
board = Board.objects.create(project=project, name="Backup test board")
column = Column.objects.create(board=board, name="К выполнению", position=0, workflow_status="todo")
Task.objects.create(column=column, title="Backup restore smoke test", creator=user)
print("Учебные записи созданы")
'
~~~

Создай backup этой учебной базы — архив попадёт в отдельный каталог team_control_backup_fixture в R2:

~~~sh
ENV_FILE=.env.backup-test bash ./infra/scripts/backup.sh
~~~

## 5. Скачать дамп на тестовую машину и восстановить

Для скачивания настрой rclone remote R2 на тестовой машине теми же переменными окружения (не храни ключ в Git):

~~~sh
export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
export RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export RCLONE_CONFIG_R2_ENDPOINT="https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com"
export RCLONE_CONFIG_R2_REGION=auto
export RCLONE_CONFIG_R2_ACL=private
export RCLONE_CONFIG_R2_NO_CHECK_BUCKET=true

remote_dir="R2:$R2_BUCKET/$R2_PREFIX/$DB_NAME"
latest_dump="$(rclone lsf "$remote_dir" --files-only | grep -E '\.dump
~~~

Локальная машина для тестового восстановления должна иметь свободное место под один дамп. Это не занимает место на основном сервере приложения.

Восстанови архив в новую БД. Требуются два явных подтверждения — изолированный тестовый PostgreSQL и точное имя новой БД:

~~~sh
ENV_FILE=.env.backup-test \
RESTORE_TEST_DB=team_control_restore_test \
RESTORE_CONFIRM_TARGET=team_control_restore_test \
RESTORE_TEST_CLUSTER_CONFIRM=I_CONFIRMED_ISOLATED_TEST_POSTGRESQL \
bash ./infra/scripts/restore-test.sh "$test_backup_dir/$latest_dump"
~~~

Скрипт:
- проверяет checksum и структуру custom dump;
- проверяет тестовую метку исходной базы;
- отказывается, если целевая база уже существует;
- создаёт новую базу с суффиксом _restore_test;
- восстанавливает туда данные;
- не очищает и не изменяет существующие базы.

## 6. Проверить восстановленные связи через Django

На тестовой машине (переменные DB_HOST, DB_USER и DB_PASSWORD должны по-прежнему указывать на тестовый PostgreSQL):

~~~sh
DB_NAME=team_control_restore_test python backend/manage.py shell -c '
from tasks.models import WorkspaceUser, Project, Membership, Task
user = WorkspaceUser.objects.get(username="backup-smoke-user")
project = Project.objects.get(name="Backup restore fixture", owner=user)
membership = Membership.objects.get(user=user, project=project)
task = Task.objects.select_related("creator", "column__board__project__owner").get(title="Backup restore smoke test")
assert task.creator_id == user.pk
assert task.column.board.project_id == project.pk
assert task.column.board.project.owner_id == user.pk
assert membership.is_confirmed
print("OK: пользователь, проект, участие и задача восстановлены; связи сохранены")
'
~~~

Ожидаемый результат: OK. Запиши дату и время, версии PostgreSQL и фактическую продолжительность восстановления. Только после успешной проверки можно считать пробное восстановление выполненным.

Если целевая база team_control_restore_test уже существует, скрипт остановится. Не удаляй её автоматически; любое удаление тестовой базы — только после ручной проверки её имени и назначения.

## 7. Ежедневный запуск через systemd

Сначала вручную добейся успешного backup и тестового восстановления. Затем на Linux-сервере создай unit-файлы (пути и пользователя замени фактическими).

/etc/systemd/system/team-control-backup.service:

~~~ini
[Unit]
Description=Team Control PostgreSQL backup to Cloudflare R2
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=<пользователь-сервиса>
Group=<группа-сервиса>
WorkingDirectory=/opt/team-control
Environment=ENV_FILE=/opt/team-control/.env.server
ExecStart=/bin/bash /opt/team-control/infra/scripts/backup.sh
UMask=0077
~~~

/etc/systemd/system/team-control-backup.timer:

~~~ini
[Unit]
Description=Daily Team Control PostgreSQL backup

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true
RandomizedDelaySec=15m
Unit=team-control-backup.service

[Install]
WantedBy=timers.target
~~~

Включение и проверка:

~~~sh
sudo systemctl daemon-reload
sudo systemctl enable --now team-control-backup.timer
sudo systemctl list-timers team-control-backup.timer
sudo systemctl start team-control-backup.service
sudo systemctl status team-control-backup.service --no-pager
sudo journalctl -u team-control-backup.service -n 50 --no-pager
~~~

Расписание считается проверенным только после успешного запуска timer и появления новой копии, checksum и metadata в R2. В учебной среде проверь отрицательный сценарий: временно укажи неверные реквизиты тестового bucket, запусти service и убедись, что systemd показывает ошибку, а старые копии не удаляются. Не ломай credentials рабочего сервера для проверки.

## 8. Ограничения и периодичность

- PostgreSQL dump содержит схему и данные базы, но не секреты, .env.server и не пользовательские файлы в R2/media. Их резервирование описывается отдельно в infra/media-backup.md и infra/object-storage.md.
- Ежедневный backup означает потенциальную потерю изменений после последней успешной копии (RPO до 24 часов).
- R2 bucket должен оставаться приватным; backup API key ограничивается только этим bucket.
- Скрипт не пишет полный архив на локальный диск сервера. Rclone использует один multipart chunk 8 MiB с одной параллельной загрузкой; при разрыве потока запуск завершается ошибкой и не сообщает об успехе.
- Восстановление проверяется вручную не реже одного раза в месяц и после существенного изменения схемы или версии PostgreSQL. Дату и длительность фиксирует ответственный.
 | LC_ALL=C sort | tail -n 1)"
test -n "$latest_dump"
test_backup_dir="$(mktemp -d)"
rclone copyto "$remote_dir/$latest_dump" "$test_backup_dir/$latest_dump"
rclone copyto "$remote_dir/$latest_dump.sha256" "$test_backup_dir/$latest_dump.sha256"
~~~

Локальная машина для тестового восстановления должна иметь свободное место под один дамп. Это не занимает место на основном сервере приложения.

Восстанови архив в новую БД. Требуются два явных подтверждения — изолированный тестовый PostgreSQL и точное имя новой БД:

~~~sh
ENV_FILE=.env.backup-test \
RESTORE_TEST_DB=team_control_restore_test \
RESTORE_CONFIRM_TARGET=team_control_restore_test \
RESTORE_TEST_CLUSTER_CONFIRM=I_CONFIRMED_ISOLATED_TEST_POSTGRESQL \
bash ./infra/scripts/restore-test.sh "./$latest_dump"
~~~

Скрипт:
- проверяет checksum и структуру custom dump;
- проверяет тестовую метку исходной базы;
- отказывается, если целевая база уже существует;
- создаёт новую базу с суффиксом _restore_test;
- восстанавливает туда данные;
- не очищает и не изменяет существующие базы.

## 6. Проверить восстановленные связи через Django

На тестовой машине (переменные DB_HOST, DB_USER и DB_PASSWORD должны по-прежнему указывать на тестовый PostgreSQL):

~~~sh
DB_NAME=team_control_restore_test python backend/manage.py shell -c '
from tasks.models import WorkspaceUser, Project, Membership, Task
user = WorkspaceUser.objects.get(username="backup-smoke-user")
project = Project.objects.get(name="Backup restore fixture", owner=user)
membership = Membership.objects.get(user=user, project=project)
task = Task.objects.select_related("creator", "column__board__project__owner").get(title="Backup restore smoke test")
assert task.creator_id == user.pk
assert task.column.board.project_id == project.pk
assert task.column.board.project.owner_id == user.pk
assert membership.is_confirmed
print("OK: пользователь, проект, участие и задача восстановлены; связи сохранены")
'
~~~

Ожидаемый результат: OK. Запиши дату и время, версии PostgreSQL и фактическую продолжительность восстановления. Только после успешной проверки можно считать пробное восстановление выполненным.

Если целевая база team_control_restore_test уже существует, скрипт остановится. Не удаляй её автоматически; любое удаление тестовой базы — только после ручной проверки её имени и назначения.

## 7. Ежедневный запуск через systemd

Сначала вручную добейся успешного backup и тестового восстановления. Затем на Linux-сервере создай unit-файлы (пути и пользователя замени фактическими).

/etc/systemd/system/team-control-backup.service:

~~~ini
[Unit]
Description=Team Control PostgreSQL backup to Cloudflare R2
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=<пользователь-сервиса>
Group=<группа-сервиса>
WorkingDirectory=/opt/team-control
Environment=ENV_FILE=/opt/team-control/.env.server
ExecStart=/bin/bash /opt/team-control/infra/scripts/backup.sh
UMask=0077
~~~

/etc/systemd/system/team-control-backup.timer:

~~~ini
[Unit]
Description=Daily Team Control PostgreSQL backup

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true
RandomizedDelaySec=15m
Unit=team-control-backup.service

[Install]
WantedBy=timers.target
~~~

Включение и проверка:

~~~sh
sudo systemctl daemon-reload
sudo systemctl enable --now team-control-backup.timer
sudo systemctl list-timers team-control-backup.timer
sudo systemctl start team-control-backup.service
sudo systemctl status team-control-backup.service --no-pager
sudo journalctl -u team-control-backup.service -n 50 --no-pager
~~~

Расписание считается проверенным только после успешного запуска timer и появления новой копии, checksum и metadata в R2. В учебной среде проверь отрицательный сценарий: временно укажи неверные реквизиты тестового bucket, запусти service и убедись, что systemd показывает ошибку, а старые копии не удаляются. Не ломай credentials рабочего сервера для проверки.

## 8. Ограничения и периодичность

- PostgreSQL dump содержит схему и данные базы, но не секреты, .env.server и не пользовательские файлы в R2/media. Их резервирование описывается отдельно в infra/media-backup.md и infra/object-storage.md.
- Ежедневный backup означает потенциальную потерю изменений после последней успешной копии (RPO до 24 часов).
- R2 bucket должен оставаться приватным; backup API key ограничивается только этим bucket.
- Скрипт не пишет полный архив на локальный диск сервера. Rclone использует один multipart chunk 8 MiB с одной параллельной загрузкой; при разрыве потока запуск завершается ошибкой и не сообщает об успехе.
- Восстановление проверяется вручную не реже одного раза в месяц и после существенного изменения схемы или версии PostgreSQL. Дату и длительность фиксирует ответственный.
