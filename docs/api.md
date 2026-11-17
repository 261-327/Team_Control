# Контракт API для сайта и Android — BE-11

Срез: main e6a589c, проверяется по backend/tasks/api_urls.py, api.py,
serializers.py, assistant_api.py, colleagues_api.py, notifications_api.py.
Этот документ описывает существующий API, не вводит новые адреса.
Все пути ниже относительно `/api/`, завершающий `/` обязателен.
Примеры вымышленные. Project и Task целиком: examples/project.json и task.json.

## Сессия, CSRF и подключение

1. GET bootstrap/ без тела. Сохранить Set-Cookie в cookie jar.
2. POST auth/login/ с JSON username/password и X-CSRFToken из cookie csrftoken.
   Сохранить cookie промежуточной сессии; ответ — challenge, а не вошедший пользователь.
3. POST auth/verify/ с code из письма, тем же cookie jar и CSRF.
4. После успешного входа заново принять Set-Cookie: CSRF может смениться.
   Последующие запросы используют новый csrftoken. sessionId в snapshot — ID
   пользователя, не секретный идентификатор сессии и не замена sessionid cookie.
5. POST auth/logout/ требует Content-Type: application/json и тело {}.

Каждый POST/PATCH требует JSON Content-Type (кроме явно указанных multipart).
CSRF проверяется для небезопасных методов, включая DELETE и публичную авторизацию.
Web: credentials: include, существующий Next proxy. Android: persistent CookieJar,
сохранение всех Set-Cookie и заголовок X-CSRFToken; Bearer-токена здесь нет.
Не хранить реальные cookie, OTP, пароли или ключи в примерах/коллекциях.

OTP: 6 ASCII цифр строкой, срок 5 минут, resend через 60 секунд.
Неверный формат даёт 400 invalid_code_format и не расходует попытку угадывания;
неверный шестизначный код расходует одну из 5 попыток. Лимит транспорта действует
отдельно. Challenge: email, mode, expiresAt/resendAt (Unix миллисекунды), delivery.

## Обозначения ответов и прав

S — полный snapshot: version, now, sessionId, users, projects, memberships,
tasks, events, comments, materials, invitations, authChallenge. Пример оболочки
изменения: {"snapshot": S}; S — обозначение в тексте, не буквальный JSON.
P — объект из examples/project.json; T — examples/task.json.
M — подтверждённый доступ к проекту или владелец. G — владелец либо подтверждённый
координатор именно этого проекта. A — любой вошедший пользователь.
Преподаватель имеет доступ только к своим проектам, не получает глобальных прав.

Общие ошибки для закрытых методов: 401 unauthenticated, 403 csrf/forbidden,
404 not_found (объект отсутствует или скрыт), 405 method_not_allowed;
400 validation для тела/полей, 409 conflict/capacity для гонки/лимита.
Лимиты входа/почты могут вернуть 429, недоступность сервиса 503.
Точное code/message надо читать из ответа, не определять по русскому тексту.
Пример 400 — examples/error.json. CSRF middleware может отказать раньше обработчика.
Успех описанных JSON-методов — 200, в том числе создания (не предполагать 201).

## Авторизация

| Метод и путь | Входной JSON (схема, без реальных секретов) | Ответ | Доступ / особенности ошибок |
|---|---|---|---|
| GET bootstrap/ | нет | S | публичный; анониму пустые коллекции |
| POST auth/register/ | name, username, email, password, passwordConfirm: строки | challenge | публичный + CSRF; 400 валидация, 429 лимиты |
| POST auth/login/ | username, password: строки | challenge | публичный + CSRF; ошибки входа/лимиты |
| POST auth/verify/ | code: строка из полученного письма | S | промежуточная сессия; 400 invalid_code_format/validation |
| POST auth/resend/ | {} | challenge | промежуточная сессия; ранний resend — ошибка |
| POST auth/logout/ | {} | S анонимного | публичный + CSRF |
| POST auth/password-reset/ | {"email":"demo@example.test"} | {"message":"…"} | одинаковый ответ для неизвестного адреса |
| POST auth/password-reset/confirm/ | uid, token, password, passwordConfirm: строки | {"message":"…"} | токен из письма, 30 минут; сессии отзываются |
| PATCH profile/ | {"name":"Демо","bio":"Учебный профиль"} | {"snapshot":S} | A |

## Проекты, состав и роли

| Метод и путь | Вход | Ответ-пример | Права / ошибки |
|---|---|---|---|
| GET projects/ | нет | {"projects":[P]} | A; только доступные |
| GET projects/1/ | нет | {"project":P} | M; чужой — 404 |
| POST projects/ | {"name":"Демо","description":"Пример","role":{"profession":"developer","specialization":"backend","customRole":""}} | {"project":P,"snapshot":S} | A; staff может задать leaderId/teacherId |
| PATCH projects/1/settings/ | {"name":"Новое имя","description":"Описание"} (непустое подмножество) | {"snapshot":S} | G |
| PATCH projects/1/description/ | {"description":"Описание"} | {"project":P,"snapshot":S} | G |
| PATCH projects/1/ | {"leaderId":"2","teacherId":"3","confirmCoordinatorDemotion":true} | {"snapshot":S} и данные назначения | G; 409 coordinator_confirmation_required |
| DELETE projects/1/ | нет | {"snapshot":S} | G |
| GET projects/1/members/ | нет | {"projectId":"1","members":[]} | M; без пагинации, владелец включён даже без Membership |
| GET directory/?q=Демо | нет | {"projects":[]} | A; поиск только доступных проектов |
| POST projects/1/join/ | {} | error | всегда 403: самостоятельное вступление отключено |
| POST projects/1/leave/ | {} | {"snapshot":S} | M; владелец не может просто выйти |
| DELETE projects/1/members/2/ | нет | {"snapshot":S} | G; защищены назначения |
| PATCH projects/1/my-role/ | {"profession":"developer","specialization":"android","customRole":""} | {"snapshot":S} | M |
| PATCH projects/1/members/2/role/ | такой же плоский объект профессии | {"snapshot":S} | G; профессия не повышает access_role |
| POST projects/1/invitations/ | {"email":"demo@example.test"} | {"invitation":{"id":"UUID","projectId":"1","projectName":"Демо","email":"demo@example.test","createdBy":"1","expiresAt":"2026-11-24T12:00:00Z","status":"pending"},"snapshot":S} | G |
| POST invitations/UUID/ | {"role":{"profession":"designer","specialization":"","customRole":""}} | {"snapshot":S} | получатель с соответствующей почтой, действующее приглашение |
| DELETE invitations/UUID/ | нет | {"snapshot":S} | G |

Вступление только по приглашению, включая DEBUG. До принятия прав на проект нет.
Профессии: developer/designer/analyst/security/tester/other; developer требует
backend/frontend/ios/android, other требует customRole. Смена руководителя и
преподавателя через PATCH projects/:id/ имеет дополнительные подтверждения;
клиент должен повторить действующий сценарий назначения из api.py, а не повышать
права через объект профессии. Роли доступа описаны в data-model.md.

## Задачи, личный список, статусы, комментарии

| Метод и путь | Вход | Ответ | Права / ошибки |
|---|---|---|---|
| GET projects/1/tasks/?page=1&pageSize=20 | нет | {"tasks":[T],"pagination":{"page":1,"pageSize":20,"totalTasks":1,"totalPages":1}} | M |
| GET me/tasks/?page=1&pageSize=20 | нет | та же оболочка | A; только свои назначения в доступных проектах |
| GET tasks/1/ | нет | {"task":T} | M |
| POST tasks/ | {"projectId":"1","title":"Макет","description":"Пример","assigneeId":"2","deadlineAt":"2026-11-19T18:00:00+03:00","tag":"дизайн"} | {"task":T,"snapshot":S} | G; исполнитель должен иметь доступ |
| PATCH tasks/1/ | title, description, assigneeId, deadlineAt, tag (форма редактирования) | {"snapshot":S} | G; не считать произвольным частичным PATCH |
| DELETE tasks/1/ | нет | {"snapshot":S} | G |
| POST tasks/1/move/ | {"status":"in_progress"}; опционально beforeTaskId, reason, resultUrl | {"snapshot":S} | G или назначенный member по разрешённому переходу; 409 capacity/conflict |
| POST projects/1/columns/ | {"name":"Дополнительно","limit":10} | {"snapshot":S} | G |
| PATCH projects/1/columns/todo/ | {"name":"К выполнению","limit":15} | {"snapshot":S} | G; limit 1–15 |
| GET tasks/1/comments/ | нет | {"comments":[{"id":"1","taskId":"1","userId":"2","text":"Пример","createdAt":"2026-11-17T12:00:00Z"}]} | M; все комментарии, без пагинации |
| POST tasks/1/comments/ | {"text":"Пример"} | {"snapshot":S} | M; до 2000 символов |
| POST tasks/1/comments/read/ | {"lastCommentId":"1"} | {"snapshot":S} | M; чужой курсор — 404 |

Пагинация задач: page по умолчанию 1, pageSize 20, максимум 100; порядок position, pk.
Невалидные параметры/несуществующая страница — 400; пустой список имеет totalTasks=0,
totalPages=0. Проекты, состав, коллеги и комментарии не используют эту оболочку.
Статусы: todo → in_progress → in_review доступны назначенному member; done и
произвольные исправления — G. Возврат in_review → in_progress требует reason.
При переносе в todo/in_progress resultUrl и даты сдачи/приёмки очищаются, старая
ссылка сохраняется в истории. Внутри того же статуса resultUrl не меняется.
Для in_review/done допустима проверенная web-ссылка resultUrl. Не отправлять
assignee_id/due_at: действующие ключи assigneeId/deadlineAt. Даты только ISO 8601
с Z или смещением; нет срока — пустая строка. См. примеры.

## Коллеги и уведомления

| Метод и путь | Вход | Ответ | Права |
|---|---|---|---|
| GET colleagues/ | нет | {"colleagues":[],"projects":[]} | A |
| POST colleagues/ | {"username":"demo_user"} | те же списки + message | A; нельзя добавить себя |
| POST colleagues/1/respond/ | {"action":"accept"} | списки + message | сторона связи; действия accept/decline/cancel/remove по состоянию |
| POST colleagues/1/invite/ | {"projectId":"1"} | списки + message | G и подтверждённый коллега |
| GET notifications/ | нет | {"notifications":[]} | A |
| POST notifications/project/UUID/respond/ | {"action":"accept","role":{"profession":"designer","specialization":"","customRole":""}} | {"notifications":[],"snapshot":S} | только получатель; accept/decline |

Коллега: id/userId — числа, username/name/bio/state, projectIds/pendingProjectIds —
массивы чисел; state incoming/outgoing/accepted. Почта не раскрывается.
Уведомление: id, kind, title, description, createdAt; для проекта projectId,
для комментария также taskId. kind: colleague/project/legacy_project/comment.
Ответ на comment выполняется через comments/read/, не respond/.

## ИИ и вложения — реализованные маршруты

ИИ зависит от настроенного провайдера и доступности воркера; наличие маршрута
не гарантирует готовность модели. Проверки доступа выполняются повторно.

| Метод и путь | Вход | Ответ / доступ |
|---|---|---|
| GET assistant/?projectId=1 | нет | {"turns":[],"capabilities":{},"pendingAttachments":[]}; A/M для projectId |
| POST assistant/ | {"projectId":"1","message":"Сроки проекта","mode":"chat","requestId":"11111111-1111-4111-8111-111111111111","attachmentIds":[]} | {"turn":…}, дополнительные поля по выполнению; A/M |
| DELETE assistant/?projectId=1 | нет | {}; только собственная история |
| GET assistant/turns/UUID/ | нет | {"turn":…}; только свой turn и актуальный scope |
| DELETE assistant/turns/UUID/ | нет | ответ удаления turn; только свой |
| POST assistant/turns/UUID/confirm/ | {"tasks":[{"title":"Макет","description":"Пример","assigneeId":"2","deadlineAt":"2026-11-19T18:00:00+03:00","tag":"дизайн"}]} — 1–10 задач | {"turn":…, "snapshot":S}; G, подтверждение до создания |
| GET assistant/turns/UUID/image/ | нет | изображение; только свой turn |
| POST assistant/attachments/ | multipart file, projectId при проектном контексте | {"attachment":…}; A/M, загрузки должны быть включены |
| DELETE assistant/attachments/UUID/ | нет | {}; только свои вложения |
| GET assistant/attachments/UUID/download/ | нет | приватный файл; только свои вложения |

mode: chat/tasks/logo. Turn: id, message, mode, status, reply, attachments, error,
createdAt, confirmedAt. reply зависит от режима/провайдера; не трактовать его как
один фиксированный текст. requestId — UUID для повторного запроса, а не ключ доступа.
Для задач и подтверждения брать структуру подготовленного ответа и валидировать
её по assistant_actions.py; не создавать задачи из неподтверждённого ответа модели.
Ошибки: общие 400/401/403/404, 409 при конфликте состояния, ограничения провайдера
и доступности. Файловые методы используют multipart, скачивание — бинарный ответ.

## Статус и согласование

Перечисленные маршруты реализованы в указанном срезе. Не объявляем GET задач и
комментариев «планируемыми». Реальная рассылка напоминаний и её расписание —
планируются; диагностическая BE-10 не является отправкой.
Формальный sign-off BLUABICK, авторов модулей, web и Android ещё не получен.
Следует совместно проверить вход → список задач → смену статуса по backend-start.md.
