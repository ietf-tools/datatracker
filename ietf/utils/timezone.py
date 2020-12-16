# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import pytz
import datetime

from django.conf import settings
from django.utils import timezone

def local_timezone_to_utc(d):
    """Takes a naive datetime in the local timezone and returns a
    naive datetime with the corresponding UTC time."""
    local_timezone = pytz.timezone(settings.TIME_ZONE)

    d = local_timezone.localize(d).astimezone(pytz.utc)

    return d.replace(tzinfo=None)

def date2datetime(date, tz=pytz.utc):
    return tz.localize(datetime.datetime(*(date.timetuple()[:3]), 12, 0))
date2datetime12 = date2datetime
    
def date2datetime00(date, tz=pytz.utc):
    return tz.localize(datetime.datetime(*(date.timetuple()[:3]), 0, 0))

def datetime_today(tzinfo=pytz.utc):
    """
    Return a timezone-aware datetime representing today, for use
    with datetime fields representing a date.
    """
    return tzinfo.localize(datetime.datetime.combine(datetime.datetime.now(tz=tzinfo).date(), datetime.time(12)))

def datetime_today_start(tzinfo=pytz.utc):
    """
    Return a timezone-aware datetime representing today, for use
    with datetime fields representing a date.
    """
    return tzinfo.localize(datetime.datetime.combine(timezone.now().date(), datetime.time(0)))
    