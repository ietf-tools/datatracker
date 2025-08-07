# Copyright (C) 2009-2011 Umeå University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Implement some usefull functions when dealing with validity of different types of information."""
import calendar
import re
import sys
import time
from datetime import datetime
from datetime import timedelta
from typing import Dict

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
TIME_FORMAT_WITH_FRAGMENT = re.compile(
    r"^(\d{4,4}-\d{2,2}-\d{2,2}T\d{2,2}:\d{2,2}:\d{2,2})\.\d*Z$"
)


class TimeUtilError(Exception):
    pass


# ---------------------------------------------------------------------------
# I'm sure this is implemented somewhere else can't find it now though, so I
# made an attempt.,
# Implemented according to
# http://www.w3.org/TR/2001/REC-xmlschema-2-20010502/
# adding-durations-to-dateTimes


def f_quotient(arg0, arg1, arg2=0):
    if arg2:
        return int((arg0 - arg1) // (arg2 - arg1))
    elif not arg0:
        return 0
    else:
        return int(arg0 // arg1)


def modulo(arg0, arg1, arg2=0):
    if arg2:
        return ((arg0 - arg1) % (arg2 - arg1)) + arg1
    else:
        return arg0 % arg1


def maximum_day_in_month_for(year, month):
    return calendar.monthrange(year, month)[1]


D_FORMAT = [
    ("Y", "tm_year"),
    ("M", "tm_mon"),
    ("D", "tm_mday"),
    ("T", ""),
    ("H", "tm_hour"),
    ("M", "tm_min"),
    ("S", "tm_sec"),
]


def parse_duration(duration):
    # (-)PnYnMnDTnHnMnS
    index = 0
    if duration[0] == "-":
        sign = "-"
        index += 1
    else:
        sign = "+"
    assert duration[index] == "P"  # nosec
    index += 1

    dic: Dict[str, float] = dict([(typ, 0) for (code, typ) in D_FORMAT])

    for code, typ in D_FORMAT:
        if duration[index] == "-":
            raise TimeUtilError("Negation not allowed on individual items")
        if code == "T":
            if duration[index] == "T":
                index += 1
                if index == len(duration):
                    raise TimeUtilError("Not allowed to end with 'T'")
            else:
                raise TimeUtilError("Missing T")
        else:
            try:
                mod = duration[index:].index(code)
                try:
                    dic[typ] = int(duration[index : index + mod])
                except ValueError:
                    if code == "S":
                        try:
                            dic[typ] = float(duration[index : index + mod])
                        except ValueError:
                            raise TimeUtilError("Not a float")
                    else:
                        raise TimeUtilError(
                            "Fractions not allow on anything byt seconds"
                        )
                index = mod + index + 1
            except ValueError:
                dic[typ] = 0

        if index == len(duration):
            break

    return sign, dic


def add_duration(tid, duration):
    (sign, dur) = parse_duration(duration)

    if sign == "+":
        # Months
        temp = tid.tm_mon + dur["tm_mon"]
        month = modulo(temp, 1, 13)
        carry = f_quotient(temp, 1, 13)
        # Years
        year = tid.tm_year + dur["tm_year"] + carry
        # seconds
        temp = tid.tm_sec + dur["tm_sec"]
        secs = modulo(temp, 60)
        carry = f_quotient(temp, 60)
        # minutes
        temp = tid.tm_min + dur["tm_min"] + carry
        minutes = modulo(temp, 60)
        carry = f_quotient(temp, 60)
        # hours
        temp = tid.tm_hour + dur["tm_hour"] + carry
        hour = modulo(temp, 60)
        carry = f_quotient(temp, 60)
        # days
        if dur["tm_mday"] > maximum_day_in_month_for(year, month):
            temp_days = maximum_day_in_month_for(year, month)
        elif dur["tm_mday"] < 1:
            temp_days = 1
        else:
            temp_days = dur["tm_mday"]
        days = temp_days + tid.tm_mday + carry
        while True:
            if days < 1:
                pass
            elif days > maximum_day_in_month_for(year, month):
                days -= maximum_day_in_month_for(year, month)
                carry = 1
            else:
                break
            temp = month + carry
            month = modulo(temp, 1, 13)
            year += f_quotient(temp, 1, 13)

        return time.localtime(
            time.mktime((year, month, days, hour, minutes, secs, 0, 0, -1))
        )
    else:
        pass


# ---------------------------------------------------------------------------


def time_in_a_while(
    days=0, seconds=0, microseconds=0, milliseconds=0, minutes=0, hours=0, weeks=0
):
    """
    Return time in a future.

    format of timedelta::
        timedelta([days[, seconds[, microseconds[, milliseconds[,
        minutes[, hours[, weeks]]]]]]])

    :return: UTC time
    """
    delta = timedelta(days, seconds, microseconds, milliseconds, minutes, hours, weeks)
    return datetime.utcnow() + delta


def time_a_while_ago(
    days=0, seconds=0, microseconds=0, milliseconds=0, minutes=0, hours=0, weeks=0
):
    """
    Return time in past.

    format of timedelta::
        timedelta([days[, seconds[, microseconds[, milliseconds[,
        minutes[, hours[, weeks]]]]]]])
    :param days:
    :param seconds:
    :param microseconds:
    :param milliseconds:
    :param minutes:
    :param hours:
    :param weeks:
    :param time_format:
    :return: datetime instance
    """
    delta = timedelta(days, seconds, microseconds, milliseconds, minutes, hours, weeks)
    return datetime.utcnow() - delta


def in_a_while(
    days=0,
    seconds=0,
    microseconds=0,
    milliseconds=0,
    minutes=0,
    hours=0,
    weeks=0,
    time_format=TIME_FORMAT,
):
    """
    Return time in a future.

    :param days:
    :param seconds:
    :param microseconds:
    :param milliseconds:
    :param minutes:
    :param hours:
    :param weeks:
    :param time_format:
    :return: Formatet string
    """
    if not time_format:
        time_format = TIME_FORMAT

    return time_in_a_while(
        days, seconds, microseconds, milliseconds, minutes, hours, weeks
    ).strftime(time_format)


def a_while_ago(
    days=0,
    seconds=0,
    microseconds=0,
    milliseconds=0,
    minutes=0,
    hours=0,
    weeks=0,
    time_format=TIME_FORMAT,
):
    """
    Return time in past.

    :param days:
    :param seconds:
    :param microseconds:
    :param milliseconds:
    :param minutes:
    :param hours:
    :param weeks:
    :param time_format:
    :return: Formatet string
    """
    return time_a_while_ago(
        days, seconds, microseconds, milliseconds, minutes, hours, weeks
    ).strftime(time_format)


# ---------------------------------------------------------------------------


def shift_time(dtime, shift):
    """
    Add/delete an integer amount of seconds from a datetime specification.

    :param dtime: The datatime specification
    :param shift: The wanted time shift (+/-)
    :return: A shifted datatime specification
    """
    return dtime + timedelta(seconds=shift)


# ---------------------------------------------------------------------------


def str_to_time(timestr, time_format=TIME_FORMAT):
    """
    Convert string to time according to TIME_FORMAT.

    :param timestr:
    :param time_format:
    :return: UTC time
    """
    if not timestr:
        return 0
    try:
        then = time.strptime(timestr, time_format)
    except ValueError:  # assume it's a format problem
        try:
            elem = TIME_FORMAT_WITH_FRAGMENT.match(timestr)
        except Exception as exc:
            print("Exception: %s on %s" % (exc, timestr), file=sys.stderr)
            raise
        if elem is None:
            raise TimeUtilError("Error parsing time")
        then = time.strptime(elem.groups()[0] + "Z", TIME_FORMAT)

    return time.gmtime(calendar.timegm(then))


def instant(time_format=TIME_FORMAT):
    return time.strftime(time_format, time.gmtime())


# ---------------------------------------------------------------------------


def before(point):
    """Test if point datetime specification is before now."""
    if not point:
        return True

    if isinstance(point, str):
        point = str_to_time(point)
    elif isinstance(point, int):
        point = time.gmtime(point)

    return time.gmtime() < point


def after(point):
    """Test if point datetime specification is equal or after now."""
    if not point:
        return True
    else:
        return not before(point)


not_before = after

# 'not_on_or_after' is just an obscure name for 'before'
not_on_or_after = before

# a point is valid if it is now or sometime in the future, in other words,
# if it is not before now
valid = before


def later_than(after, before):
    """Test if after is really later or equal to before."""
    if isinstance(after, str):
        after = str_to_time(after)
    elif isinstance(after, int):
        after = time.gmtime(after)

    if isinstance(before, str):
        before = str_to_time(before)
    elif isinstance(before, int):
        before = time.gmtime(before)

    return after >= before


def utc_time_sans_frac():
    return int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds())


def time_sans_frac():
    return int("%d" % time.time())


def epoch_in_a_while(
    days=0, seconds=0, microseconds=0, milliseconds=0, minutes=0, hours=0, weeks=0
):
    """
    Return the number of seconds since epoch a while from now.

    :param days:
    :param seconds:
    :param microseconds:
    :param milliseconds:
    :param minutes:
    :param hours:
    :param weeks:
    :return: Seconds since epoch (1970-01-01)
    """
    dt = time_in_a_while(
        days, seconds, microseconds, milliseconds, minutes, hours, weeks
    )
    return int((dt - datetime(1970, 1, 1)).total_seconds())
