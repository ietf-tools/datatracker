import pytz
import email.utils
import datetime
import random

from django.conf import settings
from django.utils import timezone


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

def date2datetime(date, tz=pytz.utc):
    return datetime.datetime(*(date.timetuple()[:6]), tzinfo=tz)
    

def timezone_not_near_midnight():
    """Get the name of a random timezone where it's not close to midnight

    Avoids midnight +/- 1 hour.
    """
    timezone_options = pytz.common_timezones
    tzname = random.choice(timezone_options)
    right_now = timezone.now().astimezone(pytz.timezone(tzname))
    while right_now.hour < 1 or right_now.hour >= 23:
        tzname = random.choice(timezone_options)
        right_now = right_now.astimezone(pytz.timezone(tzname))
    return tzname
