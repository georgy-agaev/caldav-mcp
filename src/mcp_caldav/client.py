"""CalDAV client for calendar operations."""

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    import caldav

try:
    import caldav
    from icalendar import Alarm, vCalAddress, vText
except ImportError as err:
    raise ImportError(
        "caldav library is not installed. Install it with: pip install caldav"
    ) from err


class CalendarInfo(TypedDict):
    index: int
    name: str
    url: str


class EventAttendee(TypedDict, total=False):
    email: str
    status: str
    name: str


class EventOrganizer(TypedDict, total=False):
    email: str
    name: str


class EventRecord(TypedDict, total=False):
    uid: str
    title: str
    start: str
    end: str
    description: str
    location: str
    all_day: bool
    categories: list[str]
    priority: int | None
    recurrence: str | None
    attendees: list[EventAttendee]


class EventCreationResult(TypedDict):
    success: bool
    uid: str
    title: str
    start_time: str
    end_time: str
    calendar: str


class EventUpdateResult(TypedDict):
    success: bool
    uid: str
    title: str
    start_time: str
    end_time: str
    calendar: str


class EventDeletionResult(TypedDict):
    success: bool
    uid: str
    message: str


AttendeeInput = EventAttendee | str
OrganizerInput = EventOrganizer | str


def _escape_ical_text(value: str | Any) -> str:
    """Escape text for inclusion in iCalendar payloads."""
    if not isinstance(value, str):
        value = str(value)
    result: str = (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )
    return result


def _format_rrule(recurrence: dict) -> str:
    """
    Format recurrence rule (RRULE) from dictionary to iCalendar RRULE string.

    Args:
        recurrence: Dictionary with keys:
            - frequency: 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'
            - interval: int (optional, default 1)
            - count: int (optional, number of occurrences)
            - until: datetime or date (optional, end date)
            - byday: str (optional, e.g., 'MO,WE,FR' for Monday, Wednesday, Friday)
            - bymonthday: int (optional, day of month)
            - bymonth: int (optional, month 1-12)

    Returns:
        RRULE string for iCalendar
    """
    if not recurrence:
        return ""

    frequency = recurrence.get("frequency", "DAILY").upper()
    if frequency not in ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"]:
        raise ValueError(f"Invalid frequency: {frequency}")

    parts = [f"FREQ={frequency}"]

    interval = recurrence.get("interval", 1)
    if interval > 1:
        parts.append(f"INTERVAL={interval}")

    count = recurrence.get("count")
    if count:
        parts.append(f"COUNT={count}")

    until = recurrence.get("until")
    if until:
        if isinstance(until, datetime):
            until_str = until.strftime("%Y%m%dT%H%M%SZ")
        elif isinstance(until, date):
            until_str = until.strftime("%Y%m%d")
        else:
            until_str = str(until)
        parts.append(f"UNTIL={until_str}")

    byday = recurrence.get("byday")
    if byday:
        parts.append(f"BYDAY={byday}")

    bymonthday = recurrence.get("bymonthday")
    if bymonthday:
        parts.append(f"BYMONTHDAY={bymonthday}")

    bymonth = recurrence.get("bymonth")
    if bymonth:
        parts.append(f"BYMONTH={bymonth}")

    return f"RRULE:{';'.join(parts)}"


def _format_categories(categories: list[str]) -> str:
    """
    Format categories list to iCalendar CATEGORIES string.

    Args:
        categories: List of category strings

    Returns:
        CATEGORIES line for iCalendar
    """
    if not categories:
        return ""
    # Escape commas in categories and join with commas
    escaped = [cat.replace(",", "\\,").replace(";", "\\;") for cat in categories]
    return f"CATEGORIES:{','.join(escaped)}"


def _format_attendees(attendees: list[AttendeeInput]) -> str:
    """
    Format attendees to iCalendar ATTENDEE lines.

    Args:
        attendees: List of email strings or dicts with 'email', optional 'status',
            and optional 'name'
            Status can be: 'ACCEPTED', 'DECLINED', 'TENTATIVE', 'NEEDS-ACTION'

    Returns:
        ATTENDEE lines for iCalendar
    """
    if not attendees:
        return ""

    attendee_lines = []
    for attendee in attendees:
        display_name = ""
        if isinstance(attendee, str):
            email = attendee.strip()
            status = None
        elif isinstance(attendee, dict):
            email = attendee.get("email", "").strip()
            status = attendee.get("status", "").upper()
            display_name = attendee.get("name", email)
        else:
            # Skip invalid attendee types (should not happen with proper typing)
            continue  # type: ignore[unreachable]

        if "@" not in email:
            continue

        # Build ATTENDEE line
        cn_value = _escape_ical_text(display_name or email)
        params = ["RSVP=TRUE", f"CN={cn_value}"]
        if status and status in ["ACCEPTED", "DECLINED", "TENTATIVE", "NEEDS-ACTION"]:
            params.append(f"PARTSTAT={status}")

        attendee_line = f"ATTENDEE;{';'.join(params)}:mailto:{email}"
        attendee_lines.append(attendee_line)

    return "\n".join(attendee_lines) + "\n" if attendee_lines else ""


def _format_organizer(organizer: OrganizerInput | None) -> str:
    """
    Format organizer to an iCalendar ORGANIZER line.

    Args:
        organizer: Email string or dict with 'email' and optional 'name'

    Returns:
        ORGANIZER line for iCalendar
    """
    if not organizer:
        return ""

    if isinstance(organizer, str):
        email = organizer.strip()
        display_name = ""
    elif isinstance(organizer, dict):
        email = organizer.get("email", "").strip()
        display_name = organizer.get("name", "").strip()
    else:
        return ""

    if "@" not in email:
        return ""

    cn_value = _escape_ical_text(display_name or email)
    return f"ORGANIZER;CN={cn_value}:mailto:{email}\n"


def _build_attendee_cal_address(attendee: AttendeeInput) -> vCalAddress | None:
    if isinstance(attendee, str):
        email = attendee.strip()
        status = None
        display_name = ""
    elif isinstance(attendee, dict):
        email = attendee.get("email", "").strip()
        status = attendee.get("status", "").upper()
        display_name = attendee.get("name", "").strip()
    else:
        return None

    if "@" not in email:
        return None

    cal_address = vCalAddress(f"mailto:{email}")
    if display_name:
        cal_address.params["CN"] = vText(display_name)
    cal_address.params["RSVP"] = vText("TRUE")
    if status and status in ["ACCEPTED", "DECLINED", "TENTATIVE", "NEEDS-ACTION"]:
        cal_address.params["PARTSTAT"] = vText(status)
    return cal_address


def _build_organizer_cal_address(organizer: OrganizerInput) -> vCalAddress | None:
    if isinstance(organizer, str):
        email = organizer.strip()
        display_name = ""
    elif isinstance(organizer, dict):
        email = organizer.get("email", "").strip()
        display_name = organizer.get("name", "").strip()
    else:
        return None

    if "@" not in email:
        return None

    cal_address = vCalAddress(f"mailto:{email}")
    if display_name:
        cal_address.params["CN"] = vText(display_name)
    return cal_address


def _replace_alarm_components(
    ical_component: Any, reminders: list[dict], summary: str
) -> None:
    if not hasattr(ical_component, "subcomponents"):
        return

    ical_component.subcomponents = [
        component
        for component in ical_component.subcomponents
        if getattr(component, "name", "") != "VALARM"
    ]

    for reminder in reminders:
        minutes_before = reminder.get("minutes_before", 15)
        action = reminder.get("action", "DISPLAY").upper()
        description_text = reminder.get("description", summary)

        alarm = Alarm()
        alarm.add("ACTION", action)
        alarm.add("TRIGGER", timedelta(minutes=-minutes_before))

        if action == "DISPLAY":
            alarm.add("DESCRIPTION", description_text)
        elif action == "EMAIL":
            alarm.add("SUMMARY", summary)
            alarm.add("DESCRIPTION", description_text)
            email_to = reminder.get("email_to", "")
            if email_to:
                alarm.add("ATTENDEE", vCalAddress(f"mailto:{email_to}"))
        elif action == "AUDIO":
            alarm.add("DESCRIPTION", description_text)

        ical_component.add_component(alarm)


def _parse_categories(cats: Any) -> list[str]:
    """
    Parse categories from iCalendar component.

    Args:
        cats: CATEGORIES value from iCalendar component

    Returns:
        List of category strings
    """
    if not cats:
        return []

    categories = []
    try:
        # Handle vText objects or lists
        if hasattr(cats, "cats"):
            # Multiple categories as list
            for cat in cats.cats:
                if hasattr(cat, "value"):
                    categories.append(str(cat.value))
                else:
                    categories.append(str(cat))
        elif hasattr(cats, "value"):
            # Single category as vText
            value = cats.value
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            categories = [c.strip() for c in str(value).split(",")]
        elif isinstance(cats, list):
            # List of category objects
            for cat in cats:
                if hasattr(cat, "value"):
                    val = cat.value
                    if isinstance(val, bytes):
                        val = val.decode("utf-8")
                    categories.append(str(val))
                else:
                    categories.append(str(cat))
        else:
            # String format
            cat_str = str(cats)
            if isinstance(cats, bytes):
                cat_str = cats.decode("utf-8")
            categories = [c.strip() for c in cat_str.split(",")]
    except Exception:
        # Fallback: try to convert to string
        try:
            categories = [str(cats)]
        except Exception:
            categories = []

    return [c for c in categories if c]


def _parse_attendees(ical_component: Any) -> list[EventAttendee]:
    """
    Parse attendees from iCalendar component.

    Args:
        ical_component: iCalendar component object

    Returns:
        List of attendee dictionaries with 'email' and 'status'
    """
    attendees: list[EventAttendee] = []
    attendee_list = ical_component.get("ATTENDEE", [])
    if not isinstance(attendee_list, list):
        attendee_list = [attendee_list]

    for attendee in attendee_list:
        try:
            if hasattr(attendee, "params"):
                email = str(attendee).replace("mailto:", "")
                status = (
                    attendee.params.get("PARTSTAT", ["NEEDS-ACTION"])[0]
                    if hasattr(attendee, "params")
                    else "NEEDS-ACTION"
                )
                attendees.append({"email": email, "status": status})
            else:
                # Fallback for string format
                email = str(attendee).replace("mailto:", "").strip()
                if email:
                    attendees.append({"email": email, "status": "NEEDS-ACTION"})
        except Exception:
            continue

    return attendees


def _parse_organizer(ical_component: Any) -> EventOrganizer | None:
    """
    Parse organizer from iCalendar component.

    Args:
        ical_component: iCalendar component

    Returns:
        Organizer dictionary with 'email' and optional 'name'
    """
    organizer = ical_component.get("ORGANIZER")
    if not organizer:
        return None

    email = str(organizer).replace("mailto:", "").strip()
    if not email:
        return None

    name = ""
    if hasattr(organizer, "params"):
        cn = organizer.params.get("CN")
        if isinstance(cn, list) and cn:
            name = str(cn[0])
        elif isinstance(cn, str):
            name = cn

    result: EventOrganizer = {"email": email}
    if name:
        result["name"] = name
    return result


class CalDAVClient:
    """
    Client for working with CalDAV calendars.

    Note: Some CalDAV providers (like Yandex Calendar) have rate limiting.
    Yandex Calendar artificially slows down WebDAV operations (60 seconds per MB since 2021),
    which can cause frequent 504 timeouts, especially when creating/updating events.
    """

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
    ):
        """
        Initialize CalDAV client.

        Args:
            url: CalDAV server URL (e.g., "https://caldav.example.com/")
            username: Username for authentication
            password: Password or app password for authentication
        """
        self.url = url
        self.username = username
        self.password = password
        self.client: Any | None = None
        self.principal: Any | None = None
        # Detect Yandex Calendar for special handling
        self.is_yandex = "yandex.ru" in url.lower() or "yandex.com" in url.lower()

    def connect(self) -> bool:
        """Connect to CalDAV server."""
        try:
            self.client = caldav.DAVClient(
                url=self.url,
                username=self.username,
                password=self.password,
            )
            self.principal = self.client.principal()
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to CalDAV server: {e}") from e

    def list_calendars(self) -> list[CalendarInfo]:
        """Get list of available calendars."""
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            return [
                CalendarInfo(index=i, name=cal.name, url=str(cal.url))
                for i, cal in enumerate(calendars)
            ]
        except Exception as e:
            raise RuntimeError(f"Failed to list calendars: {e}") from e

    def create_event(
        self,
        calendar_index: int = 0,
        title: str = "Event",
        description: str = "",
        location: str = "",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        duration_hours: float = 1.0,
        reminders: list[dict] | None = None,
        attendees: list[AttendeeInput] | None = None,
        organizer: OrganizerInput | None = None,
        categories: list[str] | None = None,
        priority: int | None = None,
        recurrence: dict | None = None,
    ) -> EventCreationResult:
        """
        Create an event in the calendar.

        Args:
            calendar_index: Calendar index (default: 0)
            title: Event title
            description: Event description
            location: Event location
            start_time: Start time (default: tomorrow at 14:00)
            end_time: End time (optional, uses duration_hours if not provided)
            duration_hours: Duration in hours (used if end_time not provided)
            reminders: List of reminder dictionaries with keys:
                - minutes_before: minutes before event
                - action: 'DISPLAY', 'EMAIL', or 'AUDIO'
                - description: reminder text (optional)
            attendees: List of email addresses (str) or dicts with 'email', optional
                'name', and optional 'status' (ACCEPTED/DECLINED/TENTATIVE/NEEDS-ACTION)
            organizer: Email address (str) or dict with 'email' and optional 'name'
            categories: List of category strings
            priority: Priority 0-9 (0 = highest, 9 = lowest)
            recurrence: Dictionary with recurrence rules:
                - frequency: 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'
                - interval: int (optional, default 1)
                - count: int (optional, number of occurrences)
                - until: datetime/date (optional, end date)
                - byday: str (optional, e.g., 'MO,WE,FR')
                - bymonthday: int (optional)
                - bymonth: int (optional)

        Returns:
            Event creation metadata
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            # Set default times
            if start_time is None:
                start_time = datetime.now() + timedelta(days=1)
                start_time = start_time.replace(
                    hour=14, minute=0, second=0, microsecond=0
                )
            if end_time is None:
                end_time = start_time + timedelta(hours=duration_hours)

            # Generate unique UID
            uid = f"{int(datetime.now().timestamp())}@caldav-mcp"

            title_escaped = _escape_ical_text(title)
            description_escaped = _escape_ical_text(description)
            location_escaped = _escape_ical_text(location)

            # Format alarm components for reminders
            alarm_components = ""
            if reminders:
                for reminder in reminders:
                    minutes_before = reminder.get("minutes_before", 15)
                    action = reminder.get("action", "DISPLAY").upper()
                    description_text = _escape_ical_text(
                        reminder.get("description", title)
                    )

                    if action == "DISPLAY":
                        alarm_components += f"""BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-PT{minutes_before}M
DESCRIPTION:{description_text}
END:VALARM
"""
                    elif action == "EMAIL":
                        email_to = reminder.get("email_to", "")
                        alarm_components += f"""BEGIN:VALARM
ACTION:EMAIL
TRIGGER:-PT{minutes_before}M
SUMMARY:{title_escaped}
DESCRIPTION:{description_text}
"""
                        if email_to:
                            alarm_components += f"ATTENDEE:mailto:{email_to}\n"
                        alarm_components += "END:VALARM\n"
                    elif action == "AUDIO":
                        alarm_components += f"""BEGIN:VALARM
ACTION:AUDIO
TRIGGER:-PT{minutes_before}M
DESCRIPTION:{description_text}
END:VALARM
"""

            # Format attendee components
            attendee_components = _format_attendees(attendees) if attendees else ""

            # Format organizer (default to username if it looks like an email)
            organizer_value = organizer
            if organizer_value is None and attendees and "@" in self.username:
                organizer_value = self.username
            organizer_line = _format_organizer(organizer_value)

            # Format categories
            categories_line = _format_categories(categories) if categories else ""
            if categories_line:
                categories_line += "\n"

            # Format priority
            priority_line = f"PRIORITY:{priority}\n" if priority is not None else ""

            # Format recurrence
            rrule_line = _format_rrule(recurrence) + "\n" if recurrence else ""

            # Format iCalendar data
            vcal_data = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//CalDAV MCP Server//Python//EN
CALSCALE:GREGORIAN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}
DTSTART:{start_time.strftime("%Y%m%dT%H%M%S")}
DTEND:{end_time.strftime("%Y%m%dT%H%M%S")}
SUMMARY:{title_escaped}
DESCRIPTION:{description_escaped}
LOCATION:{location_escaped}
STATUS:CONFIRMED
SEQUENCE:0
{priority_line}{categories_line}{rrule_line}{organizer_line}{attendee_components}{alarm_components}END:VEVENT
END:VCALENDAR"""

            # Save event
            calendar.save_event(vcal_data)

            return {
                "success": True,
                "uid": uid,
                "title": title,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "calendar": calendar.name,
            }

        except Exception as e:
            raise RuntimeError(f"Failed to create event: {e}") from e

    def update_event(
        self,
        uid: str,
        calendar_index: int = 0,
        title: str | None = None,
        description: str | None = None,
        location: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        duration_hours: float | None = None,
        reminders: list[dict] | None = None,
        attendees: list[AttendeeInput] | None = None,
        organizer: OrganizerInput | None = None,
        categories: list[str] | None = None,
        priority: int | None = None,
        recurrence: dict | None = None,
    ) -> EventUpdateResult:
        """
        Update an existing event in the calendar.

        Args:
            uid: Event UID to update
            calendar_index: Calendar index (default: 0)
            title: Updated event title (optional)
            description: Updated event description (optional)
            location: Updated event location (optional)
            start_time: Updated start time (optional)
            end_time: Updated end time (optional)
            duration_hours: Duration in hours (used if end_time not provided)
            reminders: List of reminder dictionaries with keys:
                - minutes_before: minutes before event
                - action: 'DISPLAY', 'EMAIL', or 'AUDIO'
                - description: reminder text (optional)
            attendees: List of email addresses (str) or dicts with 'email', optional
                'name', and optional 'status' (ACCEPTED/DECLINED/TENTATIVE/NEEDS-ACTION)
            organizer: Email address (str) or dict with 'email' and optional 'name'
            categories: List of category strings
            priority: Priority 0-9 (0 = highest, 9 = lowest)
            recurrence: Dictionary with recurrence rules

        Returns:
            Event update metadata
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            start_date = datetime.now() - timedelta(days=365)
            end_date = datetime.now() + timedelta(days=365)
            events = calendar.date_search(start=start_date, end=end_date)

            target_event = None
            for event in events:
                try:
                    ical_component = event.icalendar_component
                    event_uid = str(ical_component.get("UID", ""))
                    if event_uid == uid:
                        target_event = event
                        break
                except Exception:
                    continue

            if not target_event:
                raise ValueError(f"Event with UID {uid} not found.")

            ical_component = target_event.icalendar_component

            if title is not None:
                ical_component["SUMMARY"] = title
            if description is not None:
                ical_component["DESCRIPTION"] = description
            if location is not None:
                ical_component["LOCATION"] = location

            if (
                start_time is not None
                or end_time is not None
                or duration_hours is not None
            ):
                existing_dtstart = ical_component.get("DTSTART")
                existing_dtend = ical_component.get("DTEND")
                existing_start = existing_dtstart.dt if existing_dtstart else None
                existing_end = existing_dtend.dt if existing_dtend else None

                new_start = start_time if start_time is not None else existing_start
                if new_start is None:
                    raise ValueError("Event start time is required to update timing.")

                if end_time is not None:
                    new_end = end_time
                elif duration_hours is not None:
                    new_end = new_start + timedelta(hours=duration_hours)
                elif existing_start and existing_end:
                    new_end = new_start + (existing_end - existing_start)
                else:
                    new_end = new_start + timedelta(hours=1)

                ical_component["DTSTART"] = new_start
                ical_component["DTEND"] = new_end

            if reminders is not None:
                summary_value = str(ical_component.get("SUMMARY", ""))
                _replace_alarm_components(ical_component, reminders, summary_value)

            if categories is not None:
                ical_component.pop("CATEGORIES", None)
                if categories:
                    ical_component.add("CATEGORIES", categories)

            if priority is not None:
                ical_component["PRIORITY"] = int(priority)

            if recurrence is not None:
                ical_component.pop("RRULE", None)
                if recurrence:
                    rrule_value = _format_rrule(recurrence)
                    if rrule_value.startswith("RRULE:"):
                        rrule_value = rrule_value[len("RRULE:") :]
                    if rrule_value:
                        ical_component.add("RRULE", rrule_value)

            if attendees is not None:
                ical_component.pop("ATTENDEE", None)
                for attendee in attendees:
                    cal_address = _build_attendee_cal_address(attendee)
                    if cal_address:
                        ical_component.add("ATTENDEE", cal_address)

            existing_organizer = _parse_organizer(ical_component)
            if organizer is not None:
                ical_component.pop("ORGANIZER", None)
                organizer_address = _build_organizer_cal_address(organizer)
                if not organizer_address:
                    raise ValueError("Organizer must be a valid email address.")
                ical_component.add("ORGANIZER", organizer_address)
            elif attendees is not None and not existing_organizer:
                organizer_address = _build_organizer_cal_address(self.username)
                if organizer_address:
                    ical_component.add("ORGANIZER", organizer_address)

            ical_component["DTSTAMP"] = datetime.utcnow()
            target_event.icalendar_component = ical_component
            target_event.save(increase_seqno=True)

            updated_start = ical_component.get("DTSTART")
            updated_end = ical_component.get("DTEND")
            start_value = updated_start.dt if updated_start else None
            end_value = updated_end.dt if updated_end else None

            return {
                "success": True,
                "uid": uid,
                "title": str(ical_component.get("SUMMARY", "")),
                "start_time": start_value.isoformat() if start_value else "",
                "end_time": end_value.isoformat() if end_value else "",
                "calendar": calendar.name,
            }

        except Exception as e:
            raise RuntimeError(f"Failed to update event: {e}") from e

    def get_events(
        self,
        calendar_index: int = 0,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        include_all_day: bool = True,
    ) -> list[EventRecord]:
        """
        Get events from calendar for specified period.

        Args:
            calendar_index: Calendar index (default: 0)
            start_date: Start of period (default: today 00:00)
            end_date: End of period (default: 7 days from start_date)
            include_all_day: Include all-day events

        Returns:
            List of event dictionaries
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            # Set default dates
            if start_date is None:
                start_date = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            if end_date is None:
                end_date = start_date + timedelta(days=7)

            # Search for events
            events = calendar.date_search(start=start_date, end=end_date)

            result: list[EventRecord] = []
            for event in events:
                try:
                    ical_component = event.icalendar_component

                    summary = ical_component.get("SUMMARY")
                    title = str(summary) if summary else ""

                    desc = ical_component.get("DESCRIPTION")
                    description = str(desc) if desc else ""

                    loc = ical_component.get("LOCATION")
                    location = str(loc) if loc else ""

                    dtstart = ical_component.get("DTSTART")
                    dtend = ical_component.get("DTEND")

                    if dtstart:
                        start_dt = dtstart.dt
                        if isinstance(start_dt, date) and not isinstance(
                            start_dt, datetime
                        ):
                            start_dt = datetime.combine(start_dt, datetime.min.time())
                            all_day = True
                        else:
                            all_day = False
                    else:
                        continue

                    if dtend:
                        end_dt = dtend.dt
                        if isinstance(end_dt, date) and not isinstance(
                            end_dt, datetime
                        ):
                            end_dt = datetime.combine(end_dt, datetime.max.time())
                    else:
                        end_dt = start_dt + timedelta(hours=1)

                    if not include_all_day and all_day:
                        continue

                    # Extract UID
                    uid = str(ical_component.get("UID", ""))

                    # Extract categories
                    cats = ical_component.get("CATEGORIES")
                    categories = _parse_categories(cats)

                    # Extract priority
                    priority = ical_component.get("PRIORITY")
                    priority_value = int(priority) if priority is not None else None

                    # Extract recurrence rule
                    rrule = ical_component.get("RRULE")
                    recurrence = str(rrule) if rrule else None

                    # Extract attendees
                    attendees = _parse_attendees(ical_component)

                    result.append(
                        {
                            "uid": uid,
                            "title": title,
                            "start": start_dt.isoformat(),
                            "end": end_dt.isoformat(),
                            "description": description,
                            "location": location,
                            "all_day": all_day,
                            "categories": categories,
                            "priority": priority_value,
                            "recurrence": recurrence,
                            "attendees": attendees,
                        }
                    )

                except Exception:
                    # Skip events that can't be processed
                    continue

            # Sort by start time
            result.sort(key=lambda x: x["start"])

            return result

        except Exception as e:
            raise RuntimeError(f"Failed to get events: {e}") from e

    def get_today_events(self, calendar_index: int = 0) -> list[EventRecord]:
        """Get all events for today."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        return self.get_events(calendar_index, today_start, today_end)

    def get_week_events(
        self, calendar_index: int = 0, start_from_today: bool = True
    ) -> list[EventRecord]:
        """Get all events for the week."""
        if start_from_today:
            start_date = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            today = datetime.now()
            days_since_monday = today.weekday()
            start_date = (today - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        end_date = start_date + timedelta(days=7)
        return self.get_events(calendar_index, start_date, end_date)

    def get_event_by_uid(self, uid: str, calendar_index: int = 0) -> EventRecord | None:
        """
        Get a specific event by its UID.

        Args:
            uid: Event UID
            calendar_index: Calendar index (default: 0)

        Returns:
            Event dictionary or None if not found
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            # Search for event by UID
            # Try to search in a wide date range (last year to next year)
            start_date = datetime.now() - timedelta(days=365)
            end_date = datetime.now() + timedelta(days=365)
            events = calendar.date_search(start=start_date, end=end_date)

            for event in events:
                try:
                    ical_component = event.icalendar_component
                    event_uid = str(ical_component.get("UID", ""))
                    if event_uid == uid:
                        # Parse event similar to get_events
                        summary = ical_component.get("SUMMARY")
                        title = str(summary) if summary else ""

                        desc = ical_component.get("DESCRIPTION")
                        description = str(desc) if desc else ""

                        loc = ical_component.get("LOCATION")
                        location = str(loc) if loc else ""

                        dtstart = ical_component.get("DTSTART")
                        dtend = ical_component.get("DTEND")

                        if dtstart:
                            start_dt = dtstart.dt
                            if isinstance(start_dt, date) and not isinstance(
                                start_dt, datetime
                            ):
                                start_dt = datetime.combine(
                                    start_dt, datetime.min.time()
                                )
                                all_day = True
                            else:
                                all_day = False
                        else:
                            continue

                        if dtend:
                            end_dt = dtend.dt
                            if isinstance(end_dt, date) and not isinstance(
                                end_dt, datetime
                            ):
                                end_dt = datetime.combine(end_dt, datetime.max.time())
                        else:
                            end_dt = start_dt + timedelta(hours=1)

                        # Extract additional fields
                        cats = ical_component.get("CATEGORIES")
                        categories = _parse_categories(cats)

                        priority = ical_component.get("PRIORITY")
                        priority_value = int(priority) if priority is not None else None

                        rrule = ical_component.get("RRULE")
                        recurrence = str(rrule) if rrule else None

                        attendees = _parse_attendees(ical_component)

                        return {
                            "uid": uid,
                            "title": title,
                            "start": start_dt.isoformat(),
                            "end": end_dt.isoformat(),
                            "description": description,
                            "location": location,
                            "all_day": all_day,
                            "categories": categories,
                            "priority": priority_value,
                            "recurrence": recurrence,
                            "attendees": attendees,
                        }
                except Exception:
                    continue

            return None

        except Exception as e:
            raise RuntimeError(f"Failed to get event by UID: {e}") from e

    def delete_event(self, uid: str, calendar_index: int = 0) -> EventDeletionResult:
        """
        Delete an event by its UID.

        Args:
            uid: Event UID to delete
            calendar_index: Calendar index (default: 0)

        Returns:
            Dictionary with deletion result
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            # Find the event
            start_date = datetime.now() - timedelta(days=365)
            end_date = datetime.now() + timedelta(days=365)
            events = calendar.date_search(start=start_date, end=end_date)

            for event in events:
                try:
                    ical_component = event.icalendar_component
                    event_uid = str(ical_component.get("UID", ""))
                    if event_uid == uid:
                        event.delete()
                        return {
                            "success": True,
                            "uid": uid,
                            "message": "Event deleted successfully",
                        }
                except Exception:
                    continue

            raise ValueError(f"Event with UID {uid} not found")

        except Exception as e:
            raise RuntimeError(f"Failed to delete event: {e}") from e

    def search_events(
        self,
        calendar_index: int = 0,
        query: str | None = None,
        search_fields: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[EventRecord]:
        """
        Search events by text, attendees, or location.

        Args:
            calendar_index: Calendar index (default: 0)
            query: Search query string
            search_fields: Fields to search in: 'title', 'description', 'location', 'attendees'
                If None, searches in all fields
            start_date: Start of search period (inclusive)
            end_date: End of search period (exclusive)

        Returns:
            List of matching event dictionaries
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        if start_date is None or end_date is None:
            raise ValueError(
                "Both start_date and end_date must be provided for search."
            )

        try:
            # Get events in date range

            all_events = self.get_events(
                calendar_index=calendar_index,
                start_date=start_date,
                end_date=end_date,
            )

            if not query:
                return all_events

            query_lower = query.lower()
            if search_fields is None:
                search_fields = ["title", "description", "location", "attendees"]

            results: list[EventRecord] = []
            for event in all_events:
                match = False

                if (
                    (
                        "title" in search_fields
                        and query_lower in event.get("title", "").lower()
                    )
                    or (
                        "description" in search_fields
                        and query_lower in event.get("description", "").lower()
                    )
                    or (
                        "location" in search_fields
                        and query_lower in event.get("location", "").lower()
                    )
                ):
                    match = True
                elif "attendees" in search_fields:
                    attendees = event.get("attendees") or []
                    for attendee in attendees:
                        email = attendee.get("email", "").lower()
                        if query_lower in email:
                            match = True
                            break

                if match:
                    results.append(event)

            return results

        except Exception as e:
            raise RuntimeError(f"Failed to search events: {e}") from e
