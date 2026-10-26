\# PostgreSQL для локальной разработки



\## Требования



\- Установленный Docker Desktop.

\- Запущенный Docker Engine.

\- Git и скачанный репозиторий Team\_Control.



\## 1. Подготовка настроек



Из корня репозитория создай локальный файл настроек:



```powershell

if (-not (Test-Path "infra\\\\.env")) {

	Copy-Item "infra\\\\.env.example" "infra\\\\.env"

}


