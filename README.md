# Sadaka

Django-проект для сбора пожертвований мечетям. В проекте есть публичные страницы, личный кабинет, API на DRF, админка и два Telegram-бота.

Стек:

- Django 5
- Django REST Framework
- PostgreSQL
- Redis
- Celery
- SimpleJWT
- django-filter
- drf-spectacular
- Docker Compose

## Что реализовано

- регистрация, вход, JWT, refresh/logout и профиль пользователя
- роли `user`, `mosque_admin`, `platform_admin`
- публичный каталог мечетей и страницы отдельных мечетей
- проекты сборов внутри мечетей
- разовые пожертвования и подписки
- личный кабинет с историей пожертвований и настройками профиля
- вход через Telegram-бота
- support-бот для обращений пользователей
- админка для мечетей, проектов, пожертвований, подписок, жалоб, отчётов и уведомлений
- Swagger, ReDoc и OpenAPI schema

## Структура

- `config/` - настройки проекта, URL и Celery
- `apps/` - основные Django-приложения
- `bot/` - Telegram-боты для входа и поддержки
- `common/` - общий код, который используется в разных приложениях
- `templates/landing/` - публичные HTML-страницы
- `static/landing/` - стили, JS и изображения публичной части
- `tests/` - тесты на pytest


## Локальный запуск

Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements/dev.txt
```

Создайте `.env`:

```bash
cp .env.example .env
```

По умолчанию в `.env.example` используется SQLite. Этого достаточно для быстрого локального запуска.

Примените миграции и загрузите тестовые данные:

```bash
python manage.py migrate
python manage.py seed_platform
```

Запустите сервер:

```bash
python manage.py runserver
```

Если нужен PostgreSQL локально, создайте пользователя и базу:

```sql
CREATE USER sadaka WITH PASSWORD 'sadaka';
CREATE DATABASE sadaka OWNER sadaka;
```

И укажите в `.env`:

```env
DATABASE_URL=postgres://sadaka:sadaka@127.0.0.1:5432/sadaka
REDIS_URL=redis://127.0.0.1:6379/0
```

## Docker

Подготовьте `.env`:

```bash
cp .env.example .env
```

Запуск основных сервисов:

```bash
docker compose -f docker/docker-compose.yml up --build
```

В Docker адреса сервисов уже настроены через имена контейнеров:

```env
DATABASE_URL=postgres://sadaka:sadaka@db:5432/sadaka
REDIS_URL=redis://redis:6379/0
```

Отдельный запуск Telegram-ботов:

```bash
docker compose -f docker/docker-compose.yml up -d telegram_auth_bot telegram_support_bot
```

## Полезные адреса

- Admin: `http://localhost:8000/admin/`
- Swagger: `http://localhost:8000/api/docs/swagger/`
- ReDoc: `http://localhost:8000/api/docs/redoc/`
- OpenAPI schema: `http://localhost:8000/api/schema/`
- Healthcheck: `http://localhost:8000/health/`
- Личный кабинет: `http://localhost:8000/profile/`
- Вход: `http://localhost:8000/login/`

## Проверки

Тесты:

```bash
pytest
```

Проверка Django-конфигурации:

```bash
python manage.py check
```

Проверка миграций:

```bash
python manage.py makemigrations --check --dry-run
```

Генерация OpenAPI-схемы:

```bash
python manage.py spectacular --file schema.yml
```

## Тестовые аккаунты

После `python manage.py seed_platform` доступны:

- platform admin: `admin@sadaka.local` / `admin12345`
- mosque admin: `imam@sadaka.local` / `imam12345`

## Telegram-боты

В проекте два бота:

- `auth_bot` - подтверждает вход через Telegram и выдаёт код для сайта
- `support_bot` - принимает обращения пользователей и показывает их администраторам

Нужные переменные:

- `TELEGRAM_AUTH_BOT_TOKEN`
- `TELEGRAM_AUTH_BOT_USERNAME`
- `TELEGRAM_SUPPORT_BOT_TOKEN`
- `TELEGRAM_SUPPORT_USERNAME`
- `SUPPORT_ADMIN_IDS`
- `TELEGRAM_PARTNERSHIP_USERNAME`
- `APP_BASE_URL`

Локальный запуск:

```bash
python -m bot.auth_bot
python -m bot.support_bot
```
