# Дополнительный адрес Сипи через Cloudflare Worker

Подготовлен фиксированный reverse proxy: `https://sipi.prettiqs.workers.dev` → `https://sipi-pilot.vercel.app`. Это дополнительный HTTP-вход перед уже работающим Next.js/Django, а не перенос приложения. Публикация не выполнена. Доступность workers.dev и соединение Cloudflare → Vercel ещё не проверены.

## До публикации нужно отдельное согласие

Этот Worker обрабатывает весь трафик сайта, включая введённые пользователями пароли, email, коды входа, содержимое проектов и cookies сессии. Предыдущее согласие на Cloudflare Workers AI этого не заменяет. Сначала покажи пользователю код и получи отдельное разрешение на такую обработку Cloudflare; только после этого можно публиковать Worker и менять основной адрес приложения.

Worker не содержит ключей, не хранит данные и не пишет их в собственные логи. Обработка HTTPS-трафика платформой Cloudflare при этом остаётся. SMTP/Cloudflare AI/Neon credentials остаются только в Vercel; переносить их в Worker не нужно.

## Что подготовлено

- [worker.mjs](worker.mjs) — автономный ES module для редактора Cloudflare. Оба адреса зафиксированы; произвольный upstream, hostname из запроса и параметры `url=` не выбирают другой сервер.
- [wrangler.jsonc](wrangler.jsonc) — необязательная конфигурация CLI для имени `sipi` в уже выбранном аккаунте. Никаких токенов и секретных переменных.
- [worker.test.mjs](worker.test.mjs) — локальные тесты через `node --test deploy/free/proxy/worker.test.mjs`, без сети.

Запросы к другому публичному hostname возвращают `421`. Поэтому имя и аккаунт Worker должны выдавать именно `sipi.prettiqs.workers.dev`; адреса preview и другой Cloudflare-аккаунт этим кодом не обслуживаются.

## Порядок включения после разрешения

1. В существующем Cloudflare-аккаунте выбери Workers Free, имя `sipi` и адрес `sipi.prettiqs.workers.dev`. Вставь `worker.mjs` как ES module. Не включай Paid, Storage, Cron и сторонние bindings. Собственные request logs в конфигурации выключены.
2. Установи compatibility date `2026-11-03` и compatibility flag `enable_request_signal`, как в `wrangler.jsonc`. Не добавляй DNS, маршруты или Vercel bypass tokens.
3. После отдельного разрешения опубликуй Worker.
4. В Production environment существующего Vercel Services проекта задай `FRONTEND_URL=https://sipi.prettiqs.workers.dev` и выполни Production redeploy. Переменная должна примениться к frontend и Django. Остальные ключи не меняются; backend остаётся приватным.
5. До завершения redeploy POST с workers.dev может получать CSRF `403` — это ожидаемая защита, её не отключают. После redeploy Django принимает точный Worker origin, а ссылки восстановления пароля ведут на него.
6. Сначала проверь только публичные страницы и `/api/livez`, `/api/health`, `/api/bootstrap`. Затем пользователь может создать/открыть аккаунт, самостоятельно введя пароль и код из письма.

Vercel Deployment Protection не меняется. Worker не использует bypass token и не ходит на защищённый branch alias. Если фиксированный Production origin требует авторизации Vercel, вернётся его ответ/внешнее перенаправление; Worker его не обходит.

## Сохранение поведения приложения

Worker сохраняет метод, путь, query, cookies, `Origin`, `Referer`, CSRF и заголовки `RSC`/`Next-Router-*`. Forwarded/Sipi/Vercel заголовки, присланные клиентом, удаляются; новый `X-Forwarded-Host` указывает на фиксированный публичный адрес. Next.js затем сам формирует доверенный `X-Sipi-Public-Host` из Production `FRONTEND_URL`; middleware Django проверяет его по точному списку допустимых адресов. Проверки Origin/Referer/CSRF остаются включёнными.

Тела запросов и ответов передаются потоками, без `.text()`, `.json()` и `.arrayBuffer()`. Это сохраняет SSR/RSC streaming, JS/CSS и PNG. `Content-Type`, `Content-Encoding` и `Vary` сохраняются. Несколько `Set-Cookie` не объединяются; обычные Secure/HttpOnly/SameSite cookies остаются host-only для workers.dev. Если upstream явно задал свой точный Domain, этот атрибут удаляется, остальные атрибуты остаются.

Абсолютные и protocol-relative `Location` на фиксированный Vercel origin переводятся на Worker; относительные ссылки сохраняются. Внешние redirects не выполняются на сервере: cookies не пересылаются на другой сайт. Содержимое HTML/JSON не переписывается; текущее приложение использует относительные ссылки и assets. Публичный адрес в абсолютных ссылках приложения должен задаваться через `FRONTEND_URL`.

Все ответы, включая assets, передаются с `no-store`; CDN cache API не используется. Это уменьшает риск смешивания HTML/RSC/сессий, но увеличивает количество загрузок JS/CSS. WebSocket/CONNECT в этом профиле не поддерживаются; текущий интерфейс использует HTTP. Будущие Server Actions потребуют отдельной проверки Origin/Host за двумя прокси.

## Что проверить на живом адресе

- `/login` открывается; сжатые JS/CSS из `/_next/static/` загружаются с правильными MIME и encoding. Переходы между страницами через RSC работают без полной перезагрузки/ошибок консоли.
- `/api/health` и `/api/bootstrap` возвращают JSON; `csrftoken` сохраняется для workers.dev. После входа есть отдельный Secure/HttpOnly session cookie. Пароль/код вводит пользователь; они не копируются в диагностические логи.
- Регистрация/вход, обновление страницы, выход, реальные письма и ссылка восстановления работают с Worker origin.
- POST с чужим Origin или без CSRF остаётся `403`, даже при наличии session cookie.
- ИИ создаёт проект и задачи, картинка скачивается; долгий ответ не буферизуется Worker. Ограничение размера ответа Vercel/Django сохраняется, Worker его не увеличивает.
- Нет redirects обратно на недоступный короткий Vercel domain и нет ответов с чужой сессией.

Локальные Node tests не воспроизводят полностью Workers compression, платформенные заголовки и cookies API. Они не доказывают доступность адреса из сети пользователя или фактический расход CPU в Cloudflare.

## Ограничения и отказ

[Workers Free](https://developers.cloudflare.com/workers/platform/limits/) ограничен 100 000 запросами в сутки на аккаунт и 10 ms CPU на запрос. В лимит входят HTML, JS, CSS, RSC и API; ожидание `fetch` не считается CPU. HTTP не имеет фиксированного wall-time ограничения, пока клиент подключён. Код выполняет один origin fetch без повторов, работы с БД и обработки больших тел. Реальный CPU нужно проверить по метрикам после публикации; попадание в Free нельзя обещать только по Node-тестам.

При превышении дневной квоты появляется Cloudflare `1027`, при CPU limit — `1102`. Платный план автоматически не включается кодом. Недоступный origin даёт безопасный `502`; потеря соединения может оборвать ответ ИИ, поэтому перед повторным созданием проверь историю/список проектов. Worker's streaming не отменяет ограничений времени Vercel.

Vercel видит сетевой адрес Cloudflare-прокси. Существующий trusted-IP limiter поэтому может объединить пользователей за одним IP-лимитом. Пользовательские IP-заголовки не принимаются за доказательство адреса; для безопасного восстановления исходного IP нужен отдельный подписанный канал, не включённый в этот минимальный профиль. Для маленького пилота учитывай общие лимиты, а не повышай их вслепую.

Cloudflare workers.dev тоже может быть недоступен из отдельных сетей. Этот вариант нужно проверить в браузере пользователя; он не гарантирует устранения сетевой проблемы с Vercel. До отдельного согласия и live-smoke остаётся только подготовленным вариантом.

Источники поведения: [streaming/compression](https://developers.cloudflare.com/workers/runtime-apis/fetch/#passthrough-behavior), [request cache/redirect](https://developers.cloudflare.com/workers/runtime-apis/request/), [отдельные Set-Cookie](https://developers.cloudflare.com/workers/runtime-apis/headers/#getall-method). Условия проверены 3 ноября 2026.
