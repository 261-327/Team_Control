# Проверка интеграции

## Backend

```sh
backend/.venv/bin/python backend/manage.py test tasks --settings=config.test_settings
```

Тесты изолированы от рабочей базы. Исходные HTML-сценарии проверяются с прежними URL через тестовый URLConf; новые API-сценарии используют настоящий `config.urls`, включая перенаправление корня на Next.js и CSRF.

Проверяются регистрация и вход с настоящим OTP, пять попыток, срок кода, отправка писем и откат при ошибке, сессии, доступ к проектам, роли, приглашения, материалы, профиль, цикл задачи, история, комментарии, лимиты, дополнительные старые статусы, сортировка и атомарный отказ переноса.

## Браузерные тесты с настоящим Django

Нужен Chromium для Playwright: `cd frontend && npx playwright install chromium`.

Останови обычные локальные серверы, чтобы освободить порты 8000 и 3000. Из корня репозитория:

```sh
mkdir -p /tmp/sipi-e2e-mail
DB_ENGINE=sqlite DB_NAME=/tmp/sipi-e2e.sqlite3 \
  backend/.venv/bin/python backend/manage.py migrate
DB_ENGINE=sqlite DB_NAME=/tmp/sipi-e2e.sqlite3 \
  EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend \
  EMAIL_FILE_PATH=/tmp/sipi-e2e-mail \
  backend/.venv/bin/python backend/manage.py runserver 127.0.0.1:8000 --noreload
```

В другом терминале:

```sh
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

В третьем:

```sh
cd frontend
SIPI_TEST_MAIL_DIR=/tmp/sipi-e2e-mail npm run test:e2e
```

Тесты создают отдельные аккаунты через настоящие формы, получают код только из каталога писем тестового Django и работают с реальной базой. Обхода авторизации и публичного API для получения OTP нет. Тестовые записи не попадают в `backend/local.sqlite3`. Подставь новые временные пути, если нужна полностью новая тестовая база.

Проверки охватывают работу владельца и участника в отдельных браузерных сессиях, приглашение и вступление, создание задачи, отправку, доработку и приёмку, комментарии, перезагрузку, перетаскивание и порядок, отказ заполненной колонки, сохранение черновика при сетевой ошибке, выход, материалы, профиль, настройки, мобильные размеры и управление диалогами с клавиатуры.

## Ручная проверка

Запусти `./start.sh`, зарегистрируй свой аккаунт, создай проект и задачу. После перезагрузки данные должны сохраниться. В другом браузере зарегистрируй второго участника с почтой приглашения и проверь вступление. Перенеси задачу на доске, обнови страницу и проверь статус. Код входа выводится в терминал только при локальном console-backend; с SMTP придёт письмо.

## Проверка локального ИИ

Дополнительно запусти оба обработчика `assistant_worker` с той же изолированной тестовой базой (не с рабочей `local.sqlite3`). Для режима logo задай `ASSISTANT_IMAGES_ENABLED=true` и `ASSISTANT_IMAGE_MODEL` на каталог скачанных весов; этот же флаг нужен тестовому Django. Ollama должна содержать Qwen3.

```sh
cd frontend
SIPI_TEST_MAIL_DIR=/tmp/sipi-e2e-mail SIPI_TEST_AI=1 npm run test:e2e -- e2e/assistant.spec.ts
```

Эти проверки используют настоящие локальные модели: создание проекта с тремя задачами прямо из чата, добавление ещё двух в тот же проект, отсутствие дублей после обновления страницы, ответ со ссылкой на существующую задачу, три новых задачи с описаниями, отсутствие записей до подтверждения, редактирование и выбор одной задачи, сохранение на доске и восстановление истории, настоящий PNG, скачивание и удаление картинки вместе с историей. Без `SIPI_TEST_AI=1` три ресурсоёмких сценария пропускаются; обычные проверки приложения работают без моделей.

## Сброс пароля (изолированная E2E-база)

Для проверки сценария сброса создай отдельную SQLite-базу и отдельный каталог писем; не используй локальную или рабочую БД:

```sh
mkdir -p /tmp/sipi-password-reset-mail
DB_ENGINE=sqlite DB_NAME=/tmp/sipi-password-reset-e2e.sqlite3 backend/.venv/bin/python backend/manage.py migrate
DB_ENGINE=sqlite DB_NAME=/tmp/sipi-password-reset-e2e.sqlite3 EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend EMAIL_FILE_PATH=/tmp/sipi-password-reset-mail backend/.venv/bin/python backend/manage.py runserver 127.0.0.1:8000 --noreload
```

Запусти Next.js на `127.0.0.1:3000`, затем выполни один сценарий:

```sh
cd frontend
SIPI_TEST_MAIL_DIR=/tmp/sipi-password-reset-mail npx playwright test e2e/password-reset.spec.ts
```

Сценарий регистрирует тестового пользователя через OTP, выходит, запрашивает ссылку восстановления, читает ссылку только из тестового каталога писем, меняет пароль и проверяет последующий обычный вход с новым паролем и OTP.
