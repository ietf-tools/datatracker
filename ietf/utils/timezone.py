import pytz
import email.utils
import datetime

from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


# Default time zone for deadlines / expiration dates.
DEADLINE_TZINFO = ZoneInfo('PST8PDT')


def local_timezone_to_utc(d):
    """Takes a naive datetime in the local timezone and returns a
    naive datetime with the corresponding UTC time."""
    local_timezone = pytz.timezone(settings.TIME_ZONE)

    d = local_timezone.localize(d).astimezone(pytz.utc)

    return d.replace(tzinfo=None)

def utc_to_local_timezone(d):
    """Takes a naive datetime UTC and returns a naive datetime in the
    local time zone."""
    local_timezone = pytz.timezone(settings.TIME_ZONE)

    d = local_timezone.normalize(d.replace(tzinfo=pytz.utc).astimezone(local_timezone))

    return d.replace(tzinfo=None)

def email_time_to_local_timezone(date_string):
    """Takes a time string from an email and returns a naive datetime
    in the local time zone."""

    t = email.utils.parsedate_tz(date_string)
    d = datetime.datetime(*t[:6])

    if t[7] != None:
        d += datetime.timedelta(seconds=t[9])

    return utc_to_local_timezone(d)

def datetime_from_date(date, tz=pytz.utc):
    """Get datetime at midnight on a given date"""
    return datetime.datetime(date.year, date.month, date.day, tzinfo=tz)


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
