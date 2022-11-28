import datetime
import random

from typing import Union
from zoneinfo import available_timezones, ZoneInfo

from django.conf import settings
from django.utils import timezone


# Timezone constants - tempting to make these settings, but changing them will
# require code changes.
#
# Default time zone for deadlines / expiration dates.
DEADLINE_TZINFO = ZoneInfo('PST8PDT')

# Time zone for dates from the RPC. This value is baked into the timestamps on DocEvents
# of type="published_rfc" - see Document.pub_date() and ietf.sync.refceditor.update_docs_from_rfc_index()
# for more information about how that works.
RPC_TZINFO = ZoneInfo('PST8PDT')


def _tzinfo(tz: Union[str, datetime.tzinfo, None]):
    """Helper to convert a tz param into a tzinfo

    Accepts a tzinfo or string containing a timezone name. Defaults to UTC if tz is None.
    """
    if tz is None:
        return datetime.timezone.utc
    elif isinstance(tz, datetime.tzinfo):
        return tz
    else:
        return ZoneInfo(tz)


def make_aware(dt, tz):
    """Assign timezone to a naive datetime

    Helper to deal with both pytz and zoneinfo type time zones. Can go away when pytz is removed.
    """
    tzinfo = _tzinfo(tz)
    if hasattr(tzinfo, 'localize'):
        return tzinfo.localize(dt)  # pytz-style
    else:
        return dt.replace(tzinfo=tzinfo)  # zoneinfo- / datetime.timezone-style


def datetime_from_date(date, tz=None):
    """Get datetime at midnight on a given date"""
    # accept either pytz or zoneinfo tzinfos until we get rid of pytz
    return make_aware(datetime.datetime(date.year, date.month, date.day), _tzinfo(tz))


def datetime_today(tz=None):
    """Get a timezone-aware datetime representing midnight today

    By default, uses settings.TIME_ZONE
    For use with datetime fields representing a date.
    """
    if tz is None:
        tz = settings.TIME_ZONE
    return timezone.now().astimezone(_tzinfo(tz)).replace(hour=0, minute=0, second=0, microsecond=0)


def date_today(tz=None):
    """Get the date corresponding to the current moment

    By default, uses settings.TIME_ZONE
    Note that Dates are not themselves timezone aware.
    """
    if tz is None:
        tz = settings.TIME_ZONE
    return timezone.now().astimezone(_tzinfo(tz)).date()


def time_now(tz=None):
    """Get the "wall clock" time corresponding to the current moment

    The value returned by this data is a Time with no tzinfo attached. (Time
    objects have only limited timezone support, even if tzinfo is filled in,
    and may not behave correctly when daylight savings time shifts are relevant.)
    """
    return timezone.now().astimezone(_tzinfo(tz)).time()


def timezone_not_near_midnight():
    """Get the name of a random timezone where it's not close to midnight

    Avoids midnight +/- 1 hour. Raises RuntimeError if it is unable to find
    a time zone satisfying this constraint.
    """
    timezone_options = list(
        available_timezones().difference(['Factory', 'localtime'])  # these two are not known to pytz
    )
    tzname = random.choice(timezone_options)
    right_now = timezone.now().astimezone(ZoneInfo(tzname))
    # Avoid the remote possibility of an infinite loop (might come up
    # if there is a problem with the time zone library)
    tries_left = 50
    while right_now.hour < 1 or right_now.hour >= 23:
        tzname = random.choice(timezone_options)
        right_now = right_now.astimezone(ZoneInfo(tzname))
        tries_left -= 1
        if tries_left <= 0:
            raise RuntimeError('Unable to find a time zone not near midnight')
    return tzname
