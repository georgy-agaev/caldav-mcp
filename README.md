# MCP CalDAV Server

Universal MCP server for CalDAV protocol integration. Works with any CalDAV-compatible calendar server including Yandex Calendar, Google Calendar (via CalDAV), Nextcloud, ownCloud, Apple iCloud, and others.

> 📖 **Quick Start**: See [QUICKSTART.md](QUICKSTART.md) for a quick guide to get started with `uv`.
> 🔧 **Cursor Setup**: See [CURSOR_SETUP.md](CURSOR_SETUP.md) for detailed Cursor IDE configuration instructions.

## Features

- List available calendars
- Create calendar events with reminders and attendees
- Get events for today, week, or custom date range
- Works with any CalDAV-compatible server (Yandex, Google, Nextcloud, ownCloud, iCloud, etc.)

## Installation

### Using uv (Recommended)

First, install uv if you haven't already:

**macOS/Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then install the project:

```bash
uv sync --dev
```

This will:

- Create a virtual environment (`.venv`)
- Install all dependencies including dev dependencies
- Generate a `uv.lock` file

### Using uvx (Run without installation)

You can also run the server directly without installing it:

```bash
uvx mcp-caldav
```

### Using pip

```bash
pip install -e .
```

## Configuration

Set the following environment variables:

```bash
export CALDAV_URL="https://caldav.example.com/"
export CALDAV_USERNAME="your-username"
export CALDAV_PASSWORD="your-password"
```

### CalDAV Server URLs

Common CalDAV server URLs:

- **Yandex Calendar**: `https://caldav.yandex.ru/`
- **Google Calendar**: `https://apidata.googleusercontent.com/caldav/v2/` (requires OAuth setup)
- **Nextcloud**: `https://your-domain.com/remote.php/dav/calendars/username/`
- **ownCloud**: `https://your-domain.com/remote.php/dav/calendars/username/`
- **Apple iCloud**: `https://caldav.icloud.com/` (requires app-specific password)
- **FastMail**: `https://caldav.fastmail.com/dav/calendars/user/`

**Note**: Some servers require app-specific passwords instead of regular passwords. Check your calendar provider's documentation for CalDAV setup instructions.

## Usage

### IDE Integration (Cursor)

To use this MCP server in Cursor:

1. Open Cursor Settings → Features → MCP Servers → + Add new global MCP server
2. Add the following configuration:

**Using uvx (Recommended - no installation needed):**

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uvx",
      "args": ["mcp-caldav"],
      "env": {
        "CALDAV_URL": "https://caldav.example.com/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

**Using local installation (after `uv sync` or `pip install`):**

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "mcp-caldav",
      "env": {
        "CALDAV_URL": "https://caldav.example.com/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

**Using local development version:**

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/caldav", "mcp-caldav"],
      "env": {
        "CALDAV_URL": "https://caldav.example.com/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

**Example for Yandex Calendar:**

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uvx",
      "args": ["mcp-caldav"],
      "env": {
        "CALDAV_URL": "https://caldav.yandex.ru/",
        "CALDAV_USERNAME": "your-username@yandex.ru",
        "CALDAV_PASSWORD": "your-app-password"
      }
    }
  }
}
```

> **⚠️ Note**: Yandex Calendar has aggressive rate limiting (60 seconds per MB since 2021).
> Write operations (create/update/delete) may experience 504 timeouts, so space out requests and introduce manual delays.
> For write-heavy workloads, consider using Google Calendar or Nextcloud instead.
> See [PROVIDER_NOTES.md](PROVIDER_NOTES.md) for details.
>
> **Testing status**: End-to-end tests currently run only against Yandex Calendar. Other CalDAV providers follow the same protocol and should work, but they have not been integration-tested yet.

**Example for Nextcloud:**

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uvx",
      "args": ["mcp-caldav"],
      "env": {
        "CALDAV_URL": "https://your-domain.com/remote.php/dav/calendars/username/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

### As MCP Server

The server can be used with MCP-compatible clients:

**Using uv (after `uv sync`):**

```bash
uv run mcp-caldav
```

**Note:** `uvx` works only with published packages from PyPI. For local development, use `uv run mcp-caldav` after `uv sync`.

**Using pip (after installation):**

```bash
mcp-caldav
```

Or with custom options:

```bash
uv run mcp-caldav --caldav-url "https://caldav.example.com/" \
                   --caldav-username "your-username" \
                   --caldav-password "your-password" \
                   --verbose
```

### Available Tools

**Basic Operations:**

- `caldav_list_calendars` - List all available calendars
- `caldav_create_event` - Create a new calendar event (supports recurrence, categories, priority, attendees, organizer)
- `caldav_get_events` - Get events for a date range (returns extended fields: UID, categories, priority, attendees, recurrence)
- `caldav_get_today_events` - Get events for today
- `caldav_get_week_events` - Get events for the week

**Advanced Operations:**

- `caldav_get_event_by_uid` - Get a specific event by its UID
- `caldav_delete_event` - Delete an event by UID
- `caldav_search_events` - Search events by text, attendees, or location

**Features Supported:**

- Recurring events (RRULE) - Daily, Weekly, Monthly, Yearly patterns
- Categories/Tags - Organize events with categories
- Priority - Set priority levels (0-9, 0 = highest)
- Attendees with statuses - Track acceptance status (ACCEPTED/DECLINED/TENTATIVE/NEEDS-ACTION)
- Organizer support - Set an explicit organizer to preserve attendees on stricter servers
- Reminders - Multiple reminders per event

## Development

### Code Quality

This project uses several tools to ensure code quality:

- **mypy** - Static type checking with strict rules
- **ruff** - Fast linting and code formatting
- **pre-commit** - Automatic checks before commits

**Run quality checks:**

```bash
# Install dev dependencies
uv sync --group dev

# Run all checks
make check

# Or individually
make lint
make format
make type-check

# Or using pre-commit
make pre-commit-run
```

**Setup pre-commit hooks:**

```bash
uv run pre-commit install
```

See [CODE_QUALITY.md](CODE_QUALITY.md) for detailed information.

### Running Tests

**Unit tests (with mocks):**

```bash
make test
# or
make test-unit
```

**E2E tests (require real CalDAV server):**

```bash
# Create .env.e2e file with your credentials, then:
make test-e2e
```

**All tests:**

```bash
make test
```

**With coverage:**

```bash
make test-cov        # Terminal report
make coverage-html   # HTML report
```

See [tests/e2e/README.md](tests/e2e/README.md) for more details on e2e tests.

### Project Structure

```
caldav/
├── src/
│   └── mcp_caldav/
│       ├── __init__.py      # Main entry point
│       ├── server.py        # MCP server implementation
│       └── client.py         # CalDAV client wrapper
├── tests/
│   ├── test_server.py       # Server unit tests
│   ├── test_client.py       # Client unit tests
│   └── e2e/                 # End-to-end tests with real server
│       ├── test_client_e2e.py
│       └── conftest.py
├── pyproject.toml           # Project configuration
├── Makefile                 # Development commands
└── README.md                # This file
```

## License

See LICENSE file for details.
