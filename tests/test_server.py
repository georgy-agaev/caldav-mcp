"""Unit tests for MCP CalDAV server."""

import json
from unittest.mock import MagicMock, patch

import pytest
from mcp.types import Tool

from mcp_caldav.server import (
    AppContext,
    call_tool,
    get_caldav_config,
    list_tools,
    server_lifespan,
)


@pytest.mark.anyio
async def test_server_lifespan():
    """Test the server_lifespan context manager."""
    with (
        patch("mcp_caldav.server.get_caldav_config") as mock_config,
        patch("mcp_caldav.server.CalDAVClient") as mock_client_cls,
    ):
        mock_config.return_value = {
            "url": "https://caldav.yandex.ru/",
            "username": "test@example.com",
            "password": "test-password",
        }
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_server = MagicMock()

        async with server_lifespan(mock_server) as ctx:
            assert isinstance(ctx, AppContext)
            assert ctx.client is not None
            mock_client.connect.assert_called_once()


@pytest.mark.anyio
async def test_server_lifespan_no_credentials():
    """Test the server_lifespan when credentials are not provided."""
    with (
        patch("mcp_caldav.server.get_caldav_config") as mock_config,
        patch("mcp_caldav.server.logger") as mock_logger,
    ):
        mock_config.return_value = {
            "url": "https://caldav.yandex.ru/",
            "username": None,
            "password": None,
        }

        mock_server = MagicMock()

        async with server_lifespan(mock_server) as ctx:
            assert isinstance(ctx, AppContext)
            assert ctx.client is None
            mock_logger.warning.assert_called()


def test_get_caldav_config():
    """Test getting CalDAV configuration from environment."""
    with patch.dict(
        "os.environ",
        {
            "CALDAV_URL": "https://test.example.com/",
            "CALDAV_USERNAME": "test@example.com",
            "CALDAV_PASSWORD": "test-password",
        },
    ):
        config = get_caldav_config()
        assert config["url"] == "https://test.example.com/"
        assert config["username"] == "test@example.com"
        assert config["password"] == "test-password"


def test_get_caldav_config_yandex_env():
    """Test getting CalDAV configuration using YANDEX_* environment variables."""
    with patch.dict(
        "os.environ",
        {
            "YANDEX_USERNAME": "test@yandex.ru",
            "YANDEX_PASSWORD": "test-password",
        },
        clear=True,  # Clear existing env vars to avoid conflicts
    ):
        config = get_caldav_config()
        assert config["username"] == "test@yandex.ru"
        assert config["password"] == "test-password"


@pytest.mark.anyio
async def test_list_tools_with_client(app_context):
    """Test listing tools when client is available."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        tools = await list_tools()

        assert isinstance(tools, list)
        assert len(tools) > 0

        for tool in tools:
            assert isinstance(tool, Tool)
            assert tool.name.startswith("caldav_")
            assert hasattr(tool, "description")
            assert hasattr(tool, "inputSchema")

        # Check that we have expected tools
        tool_names = [tool.name for tool in tools]
        assert "caldav_list_calendars" in tool_names
        assert "caldav_create_event" in tool_names
        assert "caldav_update_event" in tool_names
        assert "caldav_get_events" in tool_names
        assert "caldav_get_today_events" in tool_names
        assert "caldav_get_week_events" in tool_names


@pytest.mark.anyio
async def test_list_tools_no_client():
    """Test listing tools when client is not available."""
    from .conftest import mock_request_context

    app_context = AppContext(client=None)
    with mock_request_context(app_context):
        tools = await list_tools()
        assert isinstance(tools, list)
        assert len(tools) == 0


@pytest.mark.anyio
async def test_call_tool_list_calendars(app_context):
    """Test calling caldav_list_calendars tool."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool("caldav_list_calendars", {})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert isinstance(data, list)
        app_context.client.list_calendars.assert_called_once()


@pytest.mark.anyio
async def test_call_tool_create_event(app_context):
    """Test calling caldav_create_event tool."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_create_event",
            {
                "title": "Test Event",
                "description": "Test description",
                "location": "Test location",
            },
        )

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert data["success"] is True
        assert data["title"] == "Test Event"
        app_context.client.create_event.assert_called_once()


@pytest.mark.anyio
async def test_call_tool_create_event_with_datetime(app_context):
    """Test calling caldav_create_event tool with datetime strings."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_create_event",
            {
                "title": "Test Event",
                "start_time": "2025-01-20T14:00:00",
                "end_time": "2025-01-20T15:00:00",
            },
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["success"] is True

        # Check that create_event was called with datetime objects
        call_kwargs = app_context.client.create_event.call_args[1]
        assert call_kwargs["title"] == "Test Event"
        assert call_kwargs["start_time"] is not None
        assert call_kwargs["end_time"] is not None


@pytest.mark.anyio
async def test_call_tool_update_event(app_context):
    """Test calling caldav_update_event tool."""
    from .conftest import mock_request_context

    app_context.client.update_event.return_value = {
        "success": True,
        "uid": "test-uid",
        "title": "Updated Event",
        "start_time": "2025-01-20T14:00:00",
        "end_time": "2025-01-20T15:00:00",
        "calendar": "Test Calendar",
    }

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_update_event",
            {
                "uid": "test-uid",
                "title": "Updated Event",
                "start_time": "2025-01-20T14:00:00",
                "end_time": "2025-01-20T15:00:00",
            },
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["success"] is True

        call_kwargs = app_context.client.update_event.call_args[1]
        assert call_kwargs["uid"] == "test-uid"
        assert call_kwargs["title"] == "Updated Event"
        assert call_kwargs["start_time"] is not None
        assert call_kwargs["end_time"] is not None


@pytest.mark.anyio
async def test_call_tool_get_events(app_context):
    """Test calling caldav_get_events tool."""
    from .conftest import mock_request_context

    app_context.client.get_events.return_value = [
        {"uid": "test-uid", "title": "Test Event"},
    ]

    with mock_request_context(app_context):
        result = await call_tool("caldav_get_events", {"calendar_index": 0})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert isinstance(data, list)
        app_context.client.get_events.assert_called_once()


@pytest.mark.anyio
async def test_call_tool_get_today_events(app_context):
    """Test calling caldav_get_today_events tool."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool("caldav_get_today_events", {"calendar_index": 0})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert isinstance(data, list)
        app_context.client.get_today_events.assert_called_once()


@pytest.mark.anyio
async def test_call_tool_get_week_events(app_context):
    """Test calling caldav_get_week_events tool."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_get_week_events",
            {"calendar_index": 0, "start_from_today": True},
        )

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert isinstance(data, list)
        app_context.client.get_week_events.assert_called_once()


@pytest.mark.anyio
async def test_call_tool_no_client():
    """Test calling tool when client is not configured."""
    from .conftest import mock_request_context

    app_context = AppContext(client=None)
    with mock_request_context(app_context):
        result = await call_tool("caldav_list_calendars", {})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert "error" in data
        assert "not configured" in data["error"].lower()


@pytest.mark.anyio
async def test_call_tool_unknown_tool(app_context):
    """Test calling unknown tool."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool("unknown_tool", {})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert "error" in data
        assert "Unknown tool" in data["error"]


@pytest.mark.anyio
async def test_call_tool_error_handling(app_context):
    """Test error handling in tool calls."""
    from .conftest import mock_request_context

    app_context.client.list_calendars.side_effect = Exception("Test error")

    with mock_request_context(app_context):
        result = await call_tool("caldav_list_calendars", {})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert "error" in data
        assert "Test error" in data["error"]


@pytest.mark.anyio
async def test_call_tool_get_event_by_uid(app_context):
    """Test calling caldav_get_event_by_uid tool."""
    from .conftest import mock_request_context

    app_context.client.get_event_by_uid.return_value = {
        "uid": "test-uid",
        "title": "Test Event",
    }

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_get_event_by_uid",
            {"uid": "test-uid", "calendar_index": 0},
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["uid"] == "test-uid"
        app_context.client.get_event_by_uid.assert_called_once_with(
            uid="test-uid", calendar_index=0
        )


@pytest.mark.anyio
async def test_call_tool_get_event_by_uid_not_found(app_context):
    """Test calling caldav_get_event_by_uid when event not found."""
    from .conftest import mock_request_context

    app_context.client.get_event_by_uid.return_value = None

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_get_event_by_uid",
            {"uid": "nonexistent-uid", "calendar_index": 0},
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "error" in data
        assert "not found" in data["error"].lower()


@pytest.mark.anyio
async def test_call_tool_delete_event(app_context):
    """Test calling caldav_delete_event tool."""
    from .conftest import mock_request_context

    app_context.client.delete_event.return_value = {
        "success": True,
        "uid": "test-uid",
        "message": "Event deleted successfully",
    }

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_delete_event",
            {"uid": "test-uid", "calendar_index": 0},
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["success"] is True
        app_context.client.delete_event.assert_called_once_with(
            uid="test-uid", calendar_index=0
        )


@pytest.mark.anyio
async def test_call_tool_search_events(app_context):
    """Test calling caldav_search_events tool."""

    from .conftest import mock_request_context

    app_context.client.search_events.return_value = [
        {"uid": "uid-1", "title": "Meeting"},
    ]

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_search_events",
            {
                "query": "Meeting",
                "calendar_index": 0,
                "start_date": "2025-01-20T00:00:00",
                "end_date": "2025-01-21T00:00:00",
            },
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) == 1
        app_context.client.search_events.assert_called_once()


@pytest.mark.anyio
async def test_call_tool_create_event_with_recurrence(app_context):
    """Test calling caldav_create_event with recurrence."""
    from .conftest import mock_request_context

    app_context.client.create_event.return_value = {
        "success": True,
        "uid": "test-uid",
        "title": "Recurring Event",
    }

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_create_event",
            {
                "title": "Recurring Event",
                "recurrence": {
                    "frequency": "DAILY",
                    "count": 5,
                    "until": "2025-12-31T23:59:59",
                },
            },
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["success"] is True
        call_kwargs = app_context.client.create_event.call_args[1]
        assert call_kwargs["recurrence"] is not None
        assert call_kwargs["recurrence"]["frequency"] == "DAILY"


@pytest.mark.anyio
async def test_call_tool_create_event_with_categories_priority(app_context):
    """Test calling caldav_create_event with categories and priority."""
    from .conftest import mock_request_context

    app_context.client.create_event.return_value = {
        "success": True,
        "uid": "test-uid",
        "title": "Test Event",
    }

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_create_event",
            {
                "title": "Test Event",
                "categories": ["Work", "Important"],
                "priority": 1,
            },
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["success"] is True
        call_kwargs = app_context.client.create_event.call_args[1]
        assert call_kwargs["categories"] == ["Work", "Important"]
        assert call_kwargs["priority"] == 1


@pytest.mark.anyio
async def test_call_tool_get_events_with_dates(app_context):
    """Test calling caldav_get_events with date parameters."""
    from .conftest import mock_request_context

    app_context.client.get_events.return_value = []

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_get_events",
            {
                "calendar_index": 0,
                "start_date": "2025-01-20T00:00:00",
                "end_date": "2025-01-27T23:59:59",
                "include_all_day": False,
            },
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        call_kwargs = app_context.client.get_events.call_args[1]
        assert call_kwargs["include_all_day"] is False
        assert call_kwargs["start_date"] is not None
        assert call_kwargs["end_date"] is not None


@pytest.mark.anyio
async def test_call_tool_get_week_events_start_from_monday(app_context):
    """Test calling caldav_get_week_events starting from Monday."""
    from .conftest import mock_request_context

    app_context.client.get_week_events.return_value = []

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_get_week_events",
            {"calendar_index": 0, "start_from_today": False},
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        call_kwargs = app_context.client.get_week_events.call_args[1]
        assert call_kwargs["start_from_today"] is False


@pytest.mark.anyio
async def test_call_tool_no_client_missing_vars():
    """Test calling tool when client is not configured with missing vars."""
    from mcp_caldav.server import call_tool

    from .conftest import mock_request_context

    app_context = AppContext(client=None)
    with (
        mock_request_context(app_context),
        patch("mcp_caldav.server.get_caldav_config") as mock_config,
    ):
        mock_config.return_value = {
            "url": None,
            "username": "test@example.com",
            "password": None,
        }
        result = await call_tool("caldav_list_calendars", {})

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "error" in data
        assert "CALDAV_URL" in data["error"] or "Missing variables" in data["error"]


@pytest.mark.anyio
async def test_call_tool_create_event_with_reminders(app_context):
    """Test calling caldav_create_event with reminders."""
    from .conftest import mock_request_context

    app_context.client.create_event.return_value = {
        "success": True,
        "uid": "test-uid",
        "title": "Test Event",
    }

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_create_event",
            {
                "title": "Test Event",
                "reminders": [
                    {"minutes_before": 15, "action": "DISPLAY"},
                    {
                        "minutes_before": 60,
                        "action": "EMAIL",
                        "email_to": "test@example.com",
                    },
                ],
            },
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["success"] is True
        call_kwargs = app_context.client.create_event.call_args[1]
        assert call_kwargs["reminders"] is not None
        assert len(call_kwargs["reminders"]) == 2


@pytest.mark.anyio
async def test_call_tool_create_event_with_attendees_dict(app_context):
    """Test calling caldav_create_event with attendees as dicts."""
    from .conftest import mock_request_context

    app_context.client.create_event.return_value = {
        "success": True,
        "uid": "test-uid",
        "title": "Test Event",
    }

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_create_event",
            {
                "title": "Test Event",
                "attendees": [
                    {"email": "user1@example.com", "status": "ACCEPTED"},
                    {"email": "user2@example.com", "status": "TENTATIVE"},
                ],
            },
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["success"] is True
        call_kwargs = app_context.client.create_event.call_args[1]
        assert call_kwargs["attendees"] is not None
        assert len(call_kwargs["attendees"]) == 2
