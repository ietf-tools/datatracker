import pytz
import email.utils
import datetime

from django.conf import settings

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


