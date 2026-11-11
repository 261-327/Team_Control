# Резервное копирование и проверка восстановления PostgreSQL

## Что входит в копию

Скрипт infra/scripts/backup.sh создаёт PostgreSQL dump в формате custom (pg_dump -Fc). В копию входят схема и данные выбранной базы. Файл проверяется через pg_restore --list, для него создаётся SHA-256 и отдельный файл метаданных с датой UTC и версиями PostgreSQL.

Скрипт не копирует .env.server, пароли, настройки сервера или пользовательские файлы. Для загруженных файлов действует отдельная инструкция media-backup.md. Если используется S3/R2, резервную копию объектов нужно согласовать по времени с дампом БД; сам PostgreSQL dump не содержит байты из внешнего bucket.

## Требования к хранилищу

Резервные копии не должны занимать место на системном диске приложения и не должны попадать в Git. BACKUP_DIR должен быть корнем уже подключённого удалённого закрытого хранилища вне сервера: например, NFS/SMB, SSHFS или S3-совместимого хранилища через rclone/s3fs. Обычный локальный раздел или Docker volume не подходят.

Пример для Linux:

~~~sh
sudo mkdir -p /mnt/team-control-backups/postgres
sudo chown <пользователь-сервиса>:<группа-сервиса> /mnt/team-control-backups/postgres
sudo chmod 700 /mnt/team-control-backups/postgres
mountpoint -q /mnt/team-control-backups/postgres
findmnt /mnt/team-control-backups/postgres
~~~

Последние две команды должны подтвердить, что отдельное хранилище действительно подключено. Обычный каталог на том же сервере не считается внешней резервной копией.

До согласования места хранения не покупай платный тариф и не запускай расписание. Используй уже доступное команде закрытое хранилище. Доступ к нему должен быть только у ответственных за эксплуатацию; публичные ссылки запрещены.

## Настройка

1. Установи клиент PostgreSQL на сервере (pg_dump, pg_restore, psql, createdb). Основная версия клиента должна быть такой же или новее версии сервера. Для текущего compose.server-db.yaml используется PostgreSQL 15.
2. В защищённом .env.server добавь параметры, не коммить этот файл:

~~~dotenv
BACKUP_DIR=/mnt/team-control-backups/postgres
BACKUP_RETENTION_DAYS=7
~~~

3. Убедись, что пользователь, от имени которого запускается скрипт, может читать .env.server, подключаться к PostgreSQL и писать в BACKUP_DIR.
4. Проверь подключение к точке монтирования после перезагрузки сервера. Не запускай скрипт, если mount отсутствует: по умолчанию он откажется записывать копии на локальный диск.

Пароль БД берётся из защищённого ENV_FILE через переменную DB_PASSWORD; пароль не передаётся аргументом командной строки и не записывается в лог. Не используй set -x при запуске.

## Ручное создание копии

Из корня репозитория на сервере:

~~~sh
ENV_FILE=/opt/team-control/.env.server bash ./infra/scripts/backup.sh
~~~

Путь /opt/team-control замени на фактический каталог репозитория. Скрипт проверяет версию клиента, доступное место, успешность pg_dump, непустой архив и возможность прочитать его список объектов. Только после проверки он создаёт checksum и метаданные, а затем удаляет архивы старше BACKUP_RETENTION_DAYS. По умолчанию хранится семь дней.

Проверить последнюю копию:

~~~sh
cd /mnt/team-control-backups/postgres
sha256sum -c postgres-<имя-базы>-<дата>-<pid>.dump.sha256
pg_restore --list postgres-<имя-базы>-<дата>-<pid>.dump
cat postgres-<имя-базы>-<дата>-<pid>.dump.meta
~~~

В журнал попадает время начала/окончания и результат, но не содержимое базы, пароли или OTP-коды.

## Пробное восстановление на учебной базе

Восстановление выполняется только на отдельном PostgreSQL для тестирования. Не используй .env.server с адресом рабочей базы. Не восстанавливай архив поверх рабочей базы и не очищай существующие базы.

Ниже пример из Linux/WSL с отдельным файлом .env.backup-test, который не нужно добавлять в Git. В нём должны быть реквизиты именно изолированного тестового PostgreSQL (не production) и имя исходной базы, заканчивающееся на _backup_fixture:

~~~dotenv
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=team_control_backup_fixture
DB_USER=postgres_user
DB_PASSWORD=<пароль учебной базы>
DB_SSLMODE=prefer
BACKUP_DIR=/tmp/team-control-backups
BACKUP_RETENTION_DAYS=7
~~~

Для локальной учебной проверки каталог может быть обычным временным каталогом. Это разрешается только явным параметром BACKUP_ALLOW_LOCAL_DIR=true; на сервере этот параметр не задавай.

Сначала создай пустую учебную базу, примени миграции Django и добавь специальную метку. Метка обязательна: скрипт восстановления проверяет её до создания целевой БД, чтобы не запускаться по ошибке на production-сервере:

~~~sh
set -a
. ./.env.backup-test
set +a

PGPASSWORD="$DB_PASSWORD" createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
python backend/manage.py migrate --noinput

PGPASSWORD="$DB_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE TABLE public.backup_test_fixture (marker text PRIMARY KEY); INSERT INTO public.backup_test_fixture(marker) VALUES ('team-control-backup-test-only');"
~~~

После этого создай вымышленные связанные записи:

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

Создай копию и восстанови её в новое пустое имя с суффиксом _restore_test:

~~~sh
ENV_FILE=.env.backup-test BACKUP_ALLOW_LOCAL_DIR=true bash ./infra/scripts/backup.sh

latest_dump="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'postgres-team_control_backup_fixture-*.dump' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)"
ENV_FILE=.env.backup-test \
RESTORE_TEST_DB=team_control_restore_test \
RESTORE_CONFIRM_TARGET=team_control_restore_test \
RESTORE_TEST_CLUSTER_CONFIRM=I_CONFIRMED_ISOLATED_TEST_POSTGRESQL \
bash ./infra/scripts/restore-test.sh "$latest_dump"
~~~

После восстановления проверь связи через Django, направив Django на тестовую восстановленную базу:

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

Команды выше рассчитаны на учебный PostgreSQL, в котором уже есть тестовый пользователь Django. Не используй их против production. Если база team_control_restore_test уже существует, скрипт остановится; не удаляй её автоматически. Удалять можно только после ручной проверки, что это именно одноразовая тестовая база.

## Ежедневный запуск через systemd

Сначала вручную добейся успешного запуска и восстановления, проверь внешний mount и права. Затем добавь systemd unit на Linux-сервере. Пути и имя системного пользователя замени фактическими.

Файл /etc/systemd/system/team-control-backup.service:

~~~ini
[Unit]
Description=Team Control PostgreSQL backup
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

Файл /etc/systemd/system/team-control-backup.timer:

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

Фактическое расписание считается проверенным только после успешного запуска таймера и появления новой копии на отдельном хранилище. Проверь также неуспешный сценарий в учебной среде: отключи тестовое хранилище, запусти сервис и убедись, что systemd показывает ошибку, а старые архивы не удаляются.

## Ограничения и периодичность

- Копируются только данные PostgreSQL. Файлы из media/S3 резервируются отдельно по media-backup.md и object-storage.md.
- Секреты и .env.server не входят в дамп. Для них нужно отдельное защищённое хранение.
- При ежедневной копии возможна потеря изменений, сделанных после последнего успешного запуска. Это нормальная точка восстановления (RPO до 24 часов).
- После каждого изменения формата/версии PostgreSQL и после крупных миграций сделай дополнительную проверку восстановления.
- Ответственный вручную проверяет восстановление не реже одного раза в месяц и фиксирует дату и затраченное время.
