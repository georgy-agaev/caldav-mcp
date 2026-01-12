# Использование MCP CalDAV Server

## Установка

### Использование uv (Рекомендуется)

Сначала установите uv, если еще не установлен:

**macOS/Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Затем установите проект:

```bash
cd caldav
uv sync --dev
```

Это создаст виртуальное окружение (`.venv`), установит все зависимости и сгенерирует файл `uv.lock`.

### Использование pip

```bash
cd caldav
pip install -e .
```

## Настройка

Создайте файл `.env` или установите переменные окружения:

```bash
export CALDAV_URL="https://caldav.example.com/"
export CALDAV_USERNAME="your-username"
export CALDAV_PASSWORD="your-password"
```

### Примеры URL для популярных CalDAV серверов:

- **Yandex Calendar**: `https://caldav.yandex.ru/`
- **Nextcloud**: `https://your-domain.com/remote.php/dav/calendars/username/`
- **ownCloud**: `https://your-domain.com/remote.php/dav/calendars/username/`
- **Apple iCloud**: `https://caldav.icloud.com/` (требует app-specific password)
- **FastMail**: `https://caldav.fastmail.com/dav/calendars/user/`

**Примечание**: Некоторые серверы требуют app-specific пароли вместо обычных. Проверьте документацию вашего провайдера календаря для настройки CalDAV.

## Запуск сервера

```bash
mcp-caldav
```

Или с опциями:

```bash
uv run mcp-caldav --caldav-url "https://caldav.example.com/" \
                   --caldav-username "your-username" \
                   --caldav-password "your-password" \
                   --verbose
```

## Доступные инструменты (Tools)

### 1. caldav_list_calendars

Список всех доступных календарей.

### 2. caldav_create_event

Создание нового события в календаре.

Параметры:

- `title` (обязательный) - Название события
- `description` - Описание события
- `location` - Место проведения
- `start_time` - Время начала в формате ISO (например, "2025-01-20T14:00:00")
- `end_time` - Время окончания в формате ISO
- `duration_hours` - Продолжительность в часах (используется если end_time не указан)
- `reminders` - Список напоминаний (каждое с minutes_before, action, description)
- `attendees` - Список email-адресов участников или объектов с `email`, `status`, `name`
- `organizer` - Email организатора (строка) или объект с `email` и `name`
- `calendar_index` - Индекс календаря (по умолчанию 0)

### 3. caldav_get_events

Получение событий за указанный период.

Параметры:

- `calendar_index` - Индекс календаря (по умолчанию 0)
- `start_date` - Начало периода в формате ISO
- `end_date` - Конец периода в формате ISO
- `include_all_day` - Включать события на весь день (по умолчанию True)

### 4. caldav_get_today_events

Получение всех событий на сегодня.

Параметры:

- `calendar_index` - Индекс календаря (по умолчанию 0)

### 5. caldav_get_week_events

Получение всех событий на неделю.

Параметры:

- `calendar_index` - Индекс календаря (по умолчанию 0)
- `start_from_today` - Начинать с сегодня (True) или с понедельника (False)

## Запуск тестов

Используя Makefile (рекомендуется):

```bash
make test          # Unit tests
make test-e2e      # E2E tests (requires .env.e2e)
make test-cov      # With coverage report
make coverage-html  # HTML coverage report
```

Или напрямую:

```bash
uv run pytest tests/ -m "not e2e"  # Unit tests
make test-e2e                       # E2E tests
uv run pytest tests/ --cov=src/mcp_caldav --cov-report=html
```

## Примеры использования через MCP клиент

После запуска сервера, инструменты будут доступны через MCP-совместимые клиенты (например, Claude Desktop, Cursor и т.д.).

Пример запроса через MCP:

- Создать событие: используйте инструмент `caldav_create_event` с параметрами
- Посмотреть события на сегодня: используйте инструмент `caldav_get_today_events`
- Список календарей: используйте инструмент `caldav_list_calendars`
