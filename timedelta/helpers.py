from __future__ import division

import re
import datetime
from decimal import Decimal

from django.utils import six

STRFDATETIME = re.compile('([dgGhHis])')
STRFDATETIME_REPL = lambda x: '%%(%s)s' % x.group()

def nice_repr(timedelta, display="long", sep=", "):
    """
    Turns a datetime.timedelta object into a nice string repr.

    display can be "sql", "iso8601", "minimal", "short" or "long" [default].

    >>> from datetime import timedelta as td
    >>> nice_repr(td(days=1, hours=2, minutes=3, seconds=4))
    '1 day, 2 hours, 3 minutes, 4 seconds'
    >>> nice_repr(td(days=1, seconds=1), "minimal")
    '1d, 1s'
    >>> nice_repr(datetime.timedelta(days=1))
    '1 day'
    >>> nice_repr(datetime.timedelta(days=0))
    '0 seconds'
    >>> nice_repr(datetime.timedelta(seconds=1))
    '1 second'
    >>> nice_repr(datetime.timedelta(seconds=10))
    '10 seconds'
    >>> nice_repr(datetime.timedelta(seconds=30))
    '30 seconds'
    >>> nice_repr(datetime.timedelta(seconds=60))
    '1 minute'
    >>> nice_repr(datetime.timedelta(seconds=150))
    '2 minutes, 30 seconds'
    >>> nice_repr(datetime.timedelta(seconds=1800))
    '30 minutes'
    >>> nice_repr(datetime.timedelta(seconds=3600))
    '1 hour'
    >>> nice_repr(datetime.timedelta(seconds=3601))
    '1 hour, 1 second'
    >>> nice_repr(datetime.timedelta(seconds=19800))
    '5 hours, 30 minutes'
    >>> nice_repr(datetime.timedelta(seconds=91800))
    '1 day, 1 hour, 30 minutes'
    >>> nice_repr(datetime.timedelta(seconds=302400))
    '3 days, 12 hours'

    Tests for handling zero:
    >>> nice_repr(td(seconds=0), 'minimal')
    '0s'
    >>> nice_repr(td(seconds=0), 'short')
    '0 sec'
    >>> nice_repr(td(seconds=0), 'long')
    '0 seconds'
    """

    assert isinstance(timedelta, datetime.timedelta), "First argument must be a timedelta."

    result = []

    weeks = int(timedelta.days / 7)
    days = timedelta.days % 7
    hours = int(timedelta.seconds / 3600)
    minutes = int((timedelta.seconds % 3600) / 60)
    seconds = timedelta.seconds % 60

    if display == "sql":
        days += weeks * 7
        return "%i %02i:%02i:%02i" % (days, hours, minutes, seconds)
    elif display == "iso8601":
        return iso8601_repr(timedelta)
    elif display == 'minimal':
        words = ["w", "d", "h", "m", "s"]
    elif display == 'short':
        words = [" wks", " days", " hrs", " min", " sec"]
    elif display == 'long':
        words = [" weeks", " days", " hours", " minutes", " seconds"]
    else:
        # Use django template-style formatting.
        # Valid values are:
        # d,g,G,h,H,i,s
        return STRFDATETIME.sub(STRFDATETIME_REPL, display) % {
            'd': days,
            'g': hours,
            'G': hours if hours > 9 else '0%s' % hours,
            'h': hours,
            'H': hours if hours > 9 else '0%s' % hours,
            'i': minutes if minutes > 9 else '0%s' % minutes,
            's': seconds if seconds > 9 else '0%s' % seconds
        }

    values = [weeks, days, hours, minutes, seconds]

    for i in range(len(values)):
        if values[i]:
            if values[i] == 1 and len(words[i]) > 1:
                result.append("%i%s" % (values[i], words[i].rstrip('s')))
            else:
                result.append("%i%s" % (values[i], words[i]))

    # values with less than one second, which are considered zeroes
    if len(result) == 0:
        # display as 0 of the smallest unit
        result.append('0%s' % (words[-1]))

    return sep.join(result)


def iso8601_repr(timedelta, format=None):
    """
    Represent a timedelta as an ISO8601 duration.
    http://en.wikipedia.org/wiki/ISO_8601#Durations

    >>> from datetime import timedelta as td
    >>> iso8601_repr(td(days=1, hours=2, minutes=3, seconds=4))
    'P1DT2H3M4S'

    >>> iso8601_repr(td(hours=1, minutes=10, seconds=20), 'alt')
    'PT01:10:20'
    """
    years = int(timedelta.days / 365)
    weeks = int((timedelta.days % 365) / 7)
    days = timedelta.days % 7

    hours = int(timedelta.seconds / 3600)
    minutes = int((timedelta.seconds % 3600) / 60)
    seconds = timedelta.seconds % 60

    if format == 'alt':
        if years or weeks or days:
            raise ValueError('Does not support alt format for durations > 1 day')
        return 'PT{0:02d}:{1:02d}:{2:02d}'.format(hours, minutes, seconds)

    formatting = (
        ('P', (
            ('Y', years),
            ('W', weeks),
            ('D', days),
        )),
        ('T', (
            ('H', hours),
            ('M', minutes),
            ('S', seconds),
        )),
      )

    result = []
    for category, subcats in formatting:
        result += category
        for format, value in subcats:
            if value:
                result.append('%d%c' % (value, format))
    if result[-1] == 'T':
        result = result[:-1]

    return "".join(result)

def parse(string):
    """
    Parse a string into a timedelta object.

    >>> parse("1 day")
    datetime.timedelta(1)
    >>> parse("2 days")
    datetime.timedelta(2)
    >>> parse("1 d")
    datetime.timedelta(1)
    >>> parse("1 hour")
    datetime.timedelta(0, 3600)
    >>> parse("1 hours")
    datetime.timedelta(0, 3600)
    >>> parse("1 hr")
    datetime.timedelta(0, 3600)
    >>> parse("1 hrs")
    datetime.timedelta(0, 3600)
    >>> parse("1h")
    datetime.timedelta(0, 3600)
    >>> parse("1wk")
    datetime.timedelta(7)
    >>> parse("1 week")
    datetime.timedelta(7)
    >>> parse("1 weeks")
    datetime.timedelta(7)
    >>> parse("2 wks")
    datetime.timedelta(14)
    >>> parse("1 sec")
    datetime.timedelta(0, 1)
    >>> parse("1 secs")
    datetime.timedelta(0, 1)
    >>> parse("1 s")
    datetime.timedelta(0, 1)
    >>> parse("1 second")
    datetime.timedelta(0, 1)
    >>> parse("1 seconds")
    datetime.timedelta(0, 1)
    >>> parse("1 minute")
    datetime.timedelta(0, 60)
    >>> parse("1 min")
    datetime.timedelta(0, 60)
    >>> parse("1 m")
    datetime.timedelta(0, 60)
    >>> parse("1 minutes")
    datetime.timedelta(0, 60)
    >>> parse("1 mins")
    datetime.timedelta(0, 60)
    >>> parse("2 ws")
    Traceback (most recent call last):
    ...
    TypeError: '2 ws' is not a valid time interval
    >>> parse("2 ds")
    Traceback (most recent call last):
    ...
    TypeError: '2 ds' is not a valid time interval
    >>> parse("2 hs")
    Traceback (most recent call last):
    ...
    TypeError: '2 hs' is not a valid time interval
    >>> parse("2 ms")
    Traceback (most recent call last):
    ...
    TypeError: '2 ms' is not a valid time interval
    >>> parse("2 ss")
    Traceback (most recent call last):
    ...
    TypeError: '2 ss' is not a valid time interval
    >>> parse("")
    Traceback (most recent call last):
    ...
    TypeError: '' is not a valid time interval
    >>> parse("1.5 days")
    datetime.timedelta(1, 43200)
    >>> parse("3 weeks")
    datetime.timedelta(21)
    >>> parse("4.2 hours")
    datetime.timedelta(0, 15120)
    >>> parse(".5 hours")
    datetime.timedelta(0, 1800)
    >>> parse(" hours")
    Traceback (most recent call last):
        ...
    TypeError: 'hours' is not a valid time interval
    >>> parse("1 hour, 5 mins")
    datetime.timedelta(0, 3900)

    >>> parse("-2 days")
    datetime.timedelta(-2)
    >>> parse("-1 day 0:00:01")
    datetime.timedelta(-1, 1)
    >>> parse("-1 day, -1:01:01")
    datetime.timedelta(-2, 82739)
    >>> parse("-1 weeks, 2 days, -3 hours, 4 minutes, -5 seconds")
    datetime.timedelta(-5, 11045)

    >>> parse("0 seconds")
    datetime.timedelta(0)
    >>> parse("0 days")
    datetime.timedelta(0)
    >>> parse("0 weeks")
    datetime.timedelta(0)

    >>> zero = datetime.timedelta(0)
    >>> parse(nice_repr(zero))
    datetime.timedelta(0)
    >>> parse(nice_repr(zero, 'minimal'))
    datetime.timedelta(0)
    >>> parse(nice_repr(zero, 'short'))
    datetime.timedelta(0)
    >>> parse('  50 days 00:00:00   ')
    datetime.timedelta(50)
    """
    string = string.strip()

    if string == "":
        raise TypeError("'%s' is not a valid time interval" % string)
    # This is the format we get from sometimes Postgres, sqlite,
    # and from serialization
    d = re.match(r'^((?P<days>[-+]?\d+) days?,? )?(?P<sign>[-+]?)(?P<hours>\d+):'
                 r'(?P<minutes>\d+)(:(?P<seconds>\d+(\.\d+)?))?$',
                 six.text_type(string))
    if d:
        d = d.groupdict(0)
        if d['sign'] == '-':
            for k in 'hours', 'minutes', 'seconds':
                d[k] = '-' + d[k]
        d.pop('sign', None)
    else:
        # This is the more flexible format
        d = re.match(
                     r'^((?P<weeks>-?((\d*\.\d+)|\d+))\W*w((ee)?(k(s)?)?)(,)?\W*)?'
                     r'((?P<days>-?((\d*\.\d+)|\d+))\W*d(ay(s)?)?(,)?\W*)?'
                     r'((?P<hours>-?((\d*\.\d+)|\d+))\W*h(ou)?(r(s)?)?(,)?\W*)?'
                     r'((?P<minutes>-?((\d*\.\d+)|\d+))\W*m(in(ute)?(s)?)?(,)?\W*)?'
                     r'((?P<seconds>-?((\d*\.\d+)|\d+))\W*s(ec(ond)?(s)?)?)?\W*$',
                     six.text_type(string))
        if not d:
            raise TypeError("'%s' is not a valid time interval" % string)
        d = d.groupdict(0)

    return datetime.timedelta(**dict(( (k, float(v)) for k,v in d.items())))


def divide(obj1, obj2, as_float=False):
    """
    Allows for the division of timedeltas by other timedeltas, or by
    floats/Decimals

    >>> from datetime import timedelta as td
    >>> divide(td(1), td(1))
    1
    >>> divide(td(2), td(1))
    2
    >>> divide(td(32), 16)
    datetime.timedelta(2)
    >>> divide(datetime.timedelta(1), datetime.timedelta(hours=6))
    4
    >>> divide(datetime.timedelta(2), datetime.timedelta(3))
    0
    >>> divide(datetime.timedelta(8), datetime.timedelta(3), as_float=True)
    2.6666666666666665
    >>> divide(datetime.timedelta(8), 2.0)
    datetime.timedelta(4)
    >>> divide(datetime.timedelta(8), 2, as_float=True)
    Traceback (most recent call last):
        ...
    AssertionError: as_float=True is inappropriate when dividing timedelta by a number.

    """
    assert isinstance(obj1, datetime.timedelta), "First argument must be a timedelta."
    assert isinstance(obj2, (datetime.timedelta, int, float, Decimal)), "Second argument must be a timedelta or number"

    sec1 = obj1.days * 86400 + obj1.seconds
    if isinstance(obj2, datetime.timedelta):
        sec2 = obj2.days * 86400 + obj2.seconds
        value = sec1 / sec2
        if as_float:
            return value
        return int(value)
    else:
        if as_float:
            assert None, "as_float=True is inappropriate when dividing timedelta by a number."
        secs = sec1 / obj2
        if isinstance(secs, Decimal):
            secs = float(secs)
        return datetime.timedelta(seconds=secs)

def modulo(obj1, obj2):
    """
    Allows for remainder division of timedelta by timedelta or integer.

    >>> from datetime import timedelta as td
    >>> modulo(td(5), td(2))
    datetime.timedelta(1)
    >>> modulo(td(6), td(3))
    datetime.timedelta(0)
    >>> modulo(td(15), 4 * 3600 * 24)
    datetime.timedelta(3)

    >>> modulo(5, td(1))
    Traceback (most recent call last):
        ...
    AssertionError: First argument must be a timedelta.
    >>> modulo(td(1), 2.8)
    Traceback (most recent call last):
        ...
    AssertionError: Second argument must be a timedelta or int.
    """
    assert isinstance(obj1, datetime.timedelta), "First argument must be a timedelta."
    assert isinstance(obj2, (datetime.timedelta, int)), "Second argument must be a timedelta or int."

    sec1 = obj1.days * 86400 + obj1.seconds
    if isinstance(obj2, datetime.timedelta):
        sec2 = obj2.days * 86400 + obj2.seconds
        return datetime.timedelta(seconds=sec1 % sec2)
    else:
        return datetime.timedelta(seconds=(sec1 % obj2))

def percentage(obj1, obj2):
    """
    What percentage of obj2 is obj1? We want the answer as a float.
    >>> percentage(datetime.timedelta(4), datetime.timedelta(2))
    200.0
    >>> percentage(datetime.timedelta(2), datetime.timedelta(4))
    50.0
    """
    assert isinstance(obj1, datetime.timedelta), "First argument must be a timedelta."
    assert isinstance(obj2, datetime.timedelta), "Second argument must be a timedelta."

    return divide(obj1 * 100, obj2, as_float=True)

def decimal_percentage(obj1, obj2):
    """
    >>> decimal_percentage(datetime.timedelta(4), datetime.timedelta(2))
    Decimal('200.0')
    >>> decimal_percentage(datetime.timedelta(2), datetime.timedelta(4))
    Decimal('50.0')
    """
    return Decimal(str(percentage(obj1, obj2)))


def multiply(obj, val):
    """
    Allows for the multiplication of timedeltas by float values.
    >>> multiply(datetime.timedelta(seconds=20), 1.5)
    datetime.timedelta(0, 30)
    >>> multiply(datetime.timedelta(1), 2.5)
    datetime.timedelta(2, 43200)
    >>> multiply(datetime.timedelta(1), 3)
    datetime.timedelta(3)
    >>> multiply(datetime.timedelta(1), Decimal("5.5"))
    datetime.timedelta(5, 43200)
    >>> multiply(datetime.date.today(), 2.5)
    Traceback (most recent call last):
        ...
    AssertionError: First argument must be a timedelta.
    >>> multiply(datetime.timedelta(1), "2")
    Traceback (most recent call last):
        ...
    AssertionError: Second argument must be a number.
    """

    assert isinstance(obj, datetime.timedelta), "First argument must be a timedelta."
    assert isinstance(val, (int, float, Decimal)), "Second argument must be a number."

    sec = obj.days * 86400 + obj.seconds
    sec *= val
    if isinstance(sec, Decimal):
        sec = float(sec)
    return datetime.timedelta(seconds=sec)


def round_to_nearest(obj, timedelta):
    """
    The obj is rounded to the nearest whole number of timedeltas.

    obj can be a timedelta, datetime or time object.

    >>> round_to_nearest(datetime.datetime(2012, 1, 1, 9, 43), datetime.timedelta(1))
    datetime.datetime(2012, 1, 1, 0, 0)
    >>> round_to_nearest(datetime.datetime(2012, 1, 1, 9, 43), datetime.timedelta(hours=1))
    datetime.datetime(2012, 1, 1, 10, 0)
    >>> round_to_nearest(datetime.datetime(2012, 1, 1, 9, 43), datetime.timedelta(minutes=15))
    datetime.datetime(2012, 1, 1, 9, 45)
    >>> round_to_nearest(datetime.datetime(2012, 1, 1, 9, 43), datetime.timedelta(minutes=1))
    datetime.datetime(2012, 1, 1, 9, 43)

    >>> td = datetime.timedelta(minutes=30)
    >>> round_to_nearest(datetime.timedelta(minutes=0), td)
    datetime.timedelta(0)
    >>> round_to_nearest(datetime.timedelta(minutes=14), td)
    datetime.timedelta(0)
    >>> round_to_nearest(datetime.timedelta(minutes=15), td)
    datetime.timedelta(0, 1800)
    >>> round_to_nearest(datetime.timedelta(minutes=29), td)
    datetime.timedelta(0, 1800)
    >>> round_to_nearest(datetime.timedelta(minutes=30), td)
    datetime.timedelta(0, 1800)
    >>> round_to_nearest(datetime.timedelta(minutes=42), td)
    datetime.timedelta(0, 1800)
    >>> round_to_nearest(datetime.timedelta(hours=7, minutes=22), td)
    datetime.timedelta(0, 27000)

    >>> td = datetime.timedelta(minutes=15)
    >>> round_to_nearest(datetime.timedelta(minutes=0), td)
    datetime.timedelta(0)
    >>> round_to_nearest(datetime.timedelta(minutes=14), td)
    datetime.timedelta(0, 900)
    >>> round_to_nearest(datetime.timedelta(minutes=15), td)
    datetime.timedelta(0, 900)
    >>> round_to_nearest(datetime.timedelta(minutes=29), td)
    datetime.timedelta(0, 1800)
    >>> round_to_nearest(datetime.timedelta(minutes=30), td)
    datetime.timedelta(0, 1800)
    >>> round_to_nearest(datetime.timedelta(minutes=42), td)
    datetime.timedelta(0, 2700)
    >>> round_to_nearest(datetime.timedelta(hours=7, minutes=22), td)
    datetime.timedelta(0, 26100)

    >>> td = datetime.timedelta(minutes=30)
    >>> round_to_nearest(datetime.datetime(2010,1,1,9,22), td)
    datetime.datetime(2010, 1, 1, 9, 30)
    >>> round_to_nearest(datetime.datetime(2010,1,1,9,32), td)
    datetime.datetime(2010, 1, 1, 9, 30)
    >>> round_to_nearest(datetime.datetime(2010,1,1,9,42), td)
    datetime.datetime(2010, 1, 1, 9, 30)

    >>> round_to_nearest(datetime.time(0,20), td)
    datetime.time(0, 30)

    TODO: test with tzinfo (non-naive) datetimes/times.
    """

    assert isinstance(obj, (datetime.datetime, datetime.timedelta, datetime.time)), "First argument must be datetime, time or timedelta."
    assert isinstance(timedelta, datetime.timedelta), "Second argument must be a timedelta."

    time_only = False
    if isinstance(obj, datetime.timedelta):
        counter = datetime.timedelta(0)
    elif isinstance(obj, datetime.datetime):
        counter = datetime.datetime.combine(obj.date(), datetime.time(0, tzinfo=obj.tzinfo))
    elif isinstance(obj, datetime.time):
        counter = datetime.datetime.combine(datetime.date.today(), datetime.time(0, tzinfo=obj.tzinfo))
        obj = datetime.datetime.combine(datetime.date.today(), obj)
        time_only = True

    diff = abs(obj - counter)
    while counter < obj:
        old_diff = diff
        counter += timedelta
        diff = abs(obj - counter)

    if counter == obj:
        result = obj
    elif diff <= old_diff:
        result = counter
    else:
        result = counter - timedelta

    if time_only:
        return result.time()
    else:
        return result

def decimal_hours(timedelta, decimal_places=None):
    """
    Return a decimal value of the number of hours that this timedelta
    object refers to.
    """
    hours = Decimal(timedelta.days*24) + Decimal(timedelta.seconds) / 3600
    if decimal_places:
        return hours.quantize(Decimal(str(10**-decimal_places)))
    return hours

def week_containing(date):
    if date.weekday():
        date -= datetime.timedelta(date.weekday())

    return date, date + datetime.timedelta(6)

try:
    datetime.timedelta().total_seconds
    def total_seconds(timedelta):
        return timedelta.total_seconds()
except AttributeError:
    def total_seconds(timedelta):
        """
        Python < 2.7 does not have datetime.timedelta.total_seconds
        """
        return timedelta.days * 86400 + timedelta.seconds

if __name__ == "__main__":
    import doctest
    doctest.testmod()
