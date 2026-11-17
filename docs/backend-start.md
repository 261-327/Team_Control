# Подключение интерфейсов и порядок работы

Общий контракт: [api.md](api.md), модели: [data-model.md](data-model.md).
Фикстуры: examples/project.json, task.json, error.json. Это вымышленные объекты,
не дамп пользователей и не готовый snapshot. Подставляйте их в оболочки из api.md.

## Где код

- backend/tasks/models.py — существующие модели и ограничения БД.
- backend/tasks/serializers.py — выходной JSON/snapshot; сериализация здесь ручная,
  не Django REST Framework ModelSerializer.
- backend/tasks/api.py — JSON обработчики, проверки прав, CSRF failure и валидация.
- backend/tasks/views.py — старые HTML обработчики, не контракт мобильного API.
- backend/tasks/api_urls.py — методы /api/; backend/config/urls.py — корневой роутинг.
- backend/tasks/admin.py — административный интерфейс.
- backend/tasks/migrations/ — история схемы; новые миграции включать в Git,
  старые не переписывать. Для этой документации миграции не нужны.
- assistant_api.py / assistant_actions.py — диалоги ИИ и подтверждение действий.
- colleagues_api.py / notifications_api.py — коллеги и уведомления.

## Параллельная работа

Web и Android могут готовить типы, экраны, ошибки и cookie jar на JSON-примерах.
Бэкенд может независимо расширять модуль при сохранении существующего контракта.
Не создавать повторные User/Task или второй Django-проект. Реальная интеграция
записи зависит от миграций, действующих пользователей, подтверждённого участия и
доступного backend; ИИ дополнительно ждёт провайдера/воркера. Рассылку напоминаний
не считать готовой по диагностическому preview.

## Запуск и проверка

Локальная установка и Docker описаны в ../README.md и ../infra/README.md.
Для тестов использовать отдельные config.test_settings: они выбирают in-memory
SQLite, если TEST_POSTGRES не равен 1. Не применять тестовые настройки для сервера.
Запуск из backend (при активированном окружении и установленных requirements):

```sh
python manage.py test tasks.test_api --settings=config.test_settings
```

JSON проверять из корня репозитория:

```sh
python -m json.tool docs/examples/project.json
python -m json.tool docs/examples/task.json
python -m json.tool docs/examples/error.json
```

## Совместная приёмка (пока ожидается)

1. На отдельной БД создать вымышленного владельца, проект, участника и задачу.
2. Получить bootstrap/CSRF, выполнить login и verify через почтовый тестовый backend.
3. Принять обновлённые cookies; запросить projects/, members/, me/tasks/ и карточку.
4. От имени исполнителя перейти todo → in_progress, проверить ответ и повторный GET.
5. Проверить 401 без сессии, 403 без CSRF, 404 для чужого проекта, 400 для плохого OTP.
6. Сравнить сериализованные поля с examples; проверить offset дат и строковые ID.
7. Повторить с web и Android cookie jar; записать участников, дату, окружение и
   расхождения в PR. Не прикладывать пароли, реальные коды, cookie или токены.

Автоматический тест через Django HTTP Client подтверждает серверный сценарий,
но не заменяет совместную приёмку с представителями web/Android и BLUABICK.
