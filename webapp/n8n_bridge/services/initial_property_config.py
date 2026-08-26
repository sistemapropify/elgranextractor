"""Configuración efectiva y guardia horaria del respondedor inicial."""

import os
from datetime import time
from zoneinfo import ZoneInfo

from django.utils import timezone

from n8n_bridge.models import (
    DEFAULT_ADVISOR_MESSAGE_IN_HOURS,
    DEFAULT_ADVISOR_MESSAGE_OUT_OF_HOURS,
    PropertyBotConfiguration,
    default_property_bot_types,
)


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_time(name, default):
    raw = os.environ.get(name, default)
    hour, minute = raw.split(":", 1)
    return time(int(hour), int(minute))


def get_bot_configuration():
    defaults = {
        "enabled": _env_bool("PROPERTY_INITIAL_BOT_ENABLED", False),
        "start_time": _env_time("PROPERTY_INITIAL_BOT_START", "00:00"),
        "end_time": _env_time("PROPERTY_INITIAL_BOT_END", "05:00"),
        "office_start_time": _env_time("PROPERTY_ADVISOR_OFFICE_START", "09:00"),
        "office_end_time": _env_time("PROPERTY_ADVISOR_OFFICE_END", "18:00"),
        "timezone_name": os.environ.get("PROPERTY_INITIAL_BOT_TIMEZONE", "America/Lima"),
        "require_external_conversation_id": _env_bool(
            "PROPERTY_INITIAL_BOT_REQUIRE_CONVERSATION_ID", True
        ),
        "enabled_property_types": default_property_bot_types(),
        "captacion_delay_seconds": 60,
        "advisor_message_in_hours": os.environ.get(
            "PROPERTY_ADVISOR_MESSAGE_IN_HOURS", DEFAULT_ADVISOR_MESSAGE_IN_HOURS
        ),
        "advisor_message_out_of_hours": os.environ.get(
            "PROPERTY_ADVISOR_MESSAGE_OUT_OF_HOURS",
            DEFAULT_ADVISOR_MESSAGE_OUT_OF_HOURS,
        ),
    }
    config, _ = PropertyBotConfiguration.objects.get_or_create(singleton_key=1, defaults=defaults)
    return config


def schedule_state(config, now=None):
    tz = ZoneInfo(config.timezone_name)
    local_now = (now or timezone.now()).astimezone(tz)
    current = local_now.time().replace(tzinfo=None)
    start, end = config.start_time, config.end_time
    if start < end:
        inside = start <= current < end
    elif start > end:
        inside = current >= start or current < end
    else:
        inside = True
    return {
        "inside": inside,
        "local_now": local_now,
        "timezone": config.timezone_name,
        "start": start.strftime("%H:%M"),
        "end": end.strftime("%H:%M"),
    }


def office_schedule_state(config, now=None):
    """Estado del horario humano, independiente de la activación del bot."""
    tz = ZoneInfo(config.timezone_name)
    local_now = (now or timezone.now()).astimezone(tz)
    current = local_now.time().replace(tzinfo=None)
    start = getattr(config, "office_start_time", time(9, 0))
    end = getattr(config, "office_end_time", time(18, 0))
    if start < end:
        inside = start <= current < end
    elif start > end:
        inside = current >= start or current < end
    else:
        inside = True
    return {
        "inside": inside,
        "local_now": local_now,
        "timezone": config.timezone_name,
        "start": start.strftime("%H:%M"),
        "end": end.strftime("%H:%M"),
    }


def advisor_availability_message(config, property_reference="la propiedad", now=None):
    state = office_schedule_state(config, now=now)
    field = (
        "advisor_message_in_hours"
        if state["inside"]
        else "advisor_message_out_of_hours"
    )
    default = (
        DEFAULT_ADVISOR_MESSAGE_IN_HOURS
        if state["inside"]
        else DEFAULT_ADVISOR_MESSAGE_OUT_OF_HOURS
    )
    template = (getattr(config, field, "") or default).strip()
    return template.format(property_reference=property_reference), state
