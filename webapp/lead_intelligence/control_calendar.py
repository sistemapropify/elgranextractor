from datetime import datetime, time, timedelta
from .remarketing_engine import LIMA, as_time


def calendar_for(policy):
    return {name: getattr(policy, name) for name in ('start_hour', 'end_hour', 'weekdays', 'holidays', 'revision')}


def intervals(start, end, calendar):
    day = start.astimezone(LIMA).date()
    last = end.astimezone(LIMA).date()
    while day <= last:
        if day.weekday() in calendar['weekdays'] and day.isoformat() not in calendar['holidays']:
            begin = datetime.combine(day, time(calendar['start_hour']), tzinfo=LIMA)
            finish = datetime.combine(day, time.min, tzinfo=LIMA)+timedelta(hours=calendar['end_hour'])
            left, right = max(start, begin), min(end, finish)
            if right > left:
                yield left, right
        day += timedelta(days=1)


def business_seconds(start, end, calendar):
    return max(0, sum((right-left).total_seconds() for left, right in intervals(start, end, calendar)))


def add_minutes(start, minutes, calendar):
    start = as_time(start)
    if not calendar['weekdays'] or not 0 <= calendar['start_hour'] < calendar['end_hour'] <= 24 or minutes < 0:
        raise ValueError('Calendario inválido.')
    remaining = minutes*60
    for left, right in intervals(start, start+timedelta(days=3660), calendar):
        available = (right-left).total_seconds()
        if remaining <= available:
            return left+timedelta(seconds=remaining)
        remaining -= available
    raise ValueError('No hay horario disponible para este plazo.')
