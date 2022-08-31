import pytz
import email.utils
import datetime

from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


# Default time zone for deadlines / expiration dates.
DEADLINE_TZINFO = ZoneInfo('PST8PDT')


def make_aware(dt, tzinfo):
    """Assign timezone to a naive datetime

    Helper to deal with both pytz and zoneinfo type time zones. Can go away when pytz is removed.
    """
    if hasattr(tzinfo, 'localize'):
        return tzinfo.localize(dt)  # pytz-style
    else:
        return dt.replace(tzinfo=tzinfo)  # zoneinfo- / datetime.timezone-style


def local_timezone_to_utc(d):
    """Takes a naive datetime in the local timezone and returns a
    naive datetime with the corresponding UTC time."""
    local_timezone = pytz.timezone(settings.TIME_ZONE)

    d = local_timezone.localize(d).astimezone(pytz.utc)

    return d.replace(tzinfo=None)


def datetime_from_date(date, tz=pytz.utc):
    """Get datetime at midnight on a given date"""
    # accept either pytz or zoneinfo tzinfos until we get rid of pytz
    return make_aware(datetime.datetime(date.year, date.month, date.day), tz)


def datetime_today(tzinfo=None):
    """Get a timezone-aware datetime representing midnight today

    For use with datetime fields representing a date.
    """
    if tzinfo is None:
        tzinfo = pytz.utc
    return timezone.now().astimezone(tzinfo).replace(hour=0, minute=0, second=0, microsecond=0)


def date_today(tzinfo=None):
    """Get the date corresponding to the current moment

    Note that Dates are not themselves timezone aware.
    """
    if tzinfo is None:
        tzinfo = pytz.utc
    return timezone.now().astimezone(tzinfo).date()


def time_now(tzinfo=None):
    """Get the "wall clock" time corresponding to the current moment

    The value returned by this data is a Time with no tzinfo attached. (Time
    objects have only limited timezone support, even if tzinfo is filled in,
    and may not behave correctly when daylight savings time shifts are relevant.)
    """
    if tzinfo is None:
        tzinfo = pytz.utc
    return timezone.now().astimezone(tzinfo).time()
