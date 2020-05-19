# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import re

import debug                            # pyflakes:ignore

from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_duration

class MultiEmailField(forms.Field):
    def to_python(self, value):
        "Normalize data to a list of strings."

        # Return an empty list if no input was given.
        if not value:
            return []

        if isinstance(value, str):
            values = value.split(',')
            return [ x.strip() for x in values if x.strip() ]
        else:
            return value

    def validate(self, value):
        "Check if value consists only of valid emails."
        # Use the parent's handling of required fields, etc.
        super(MultiEmailField, self).validate(value)

        for email in value:
            validate_email(email)

def yyyymmdd_to_strftime_format(fmt):
    translation_table = sorted([
        ("yyyy", "%Y"),
        ("yy", "%y"),
        ("mm", "%m"),
        ("m", "%-m"),
        ("MM", "%B"),
        ("M", "%b"),
        ("dd", "%d"),
        ("d", "%-d"),
    ], key=lambda t: len(t[0]), reverse=True)

    res = ""
    remaining = fmt
    while remaining:
        for pattern, replacement in translation_table:
            if remaining.startswith(pattern):
                res += replacement
                remaining = remaining[len(pattern):]
                break
        else:
            res += remaining[0]
            remaining = remaining[1:]
    return res

class DatepickerDateField(forms.DateField):
    """DateField with some glue for triggering JS Bootstrap datepicker."""

    def __init__(self, date_format, picker_settings={}, *args, **kwargs):
        strftime_format = yyyymmdd_to_strftime_format(date_format)
        kwargs["input_formats"] = [strftime_format]
        kwargs["widget"] = forms.DateInput(format=strftime_format)
        super(DatepickerDateField, self).__init__(*args, **kwargs)

        self.widget.attrs["data-provide"] = "datepicker"
        self.widget.attrs["data-date-format"] = date_format
        if "placeholder" not in self.widget.attrs:
            self.widget.attrs["placeholder"] = date_format
        for k, v in picker_settings.items():
            self.widget.attrs["data-date-%s" % k] = v


# This accepts any ordered combination of labelled days, hours, minutes, seconds
ext_duration_re = re.compile(
    r'^'
    r'(?:(?P<days>-?\d+) ?(?:d|days))?'
    r'(?:[, ]*(?P<hours>-?\d+) ?(?:h|hours))?'
    r'(?:[, ]*(?P<minutes>-?\d+) ?(?:m|minutes))?'
    r'(?:[, ]*(?P<seconds>-?\d+) ?(?:s|seconds))?'
    r'$'
)
# This requires hours and minutes, and accepts optional X days and :SS
mix_duration_re = re.compile(
    r'^'
    r'(?:(?P<days>-?\d+) ?(?:d|days)[, ]*)?'
    r'(?:(?P<hours>-?\d+))'
    r'(?::(?P<minutes>-?\d+))'
    r'(?::(?P<seconds>-?\d+))?'
    r'$'
)

def parse_duration_ext(value):
    if value.strip() != '':
        match = ext_duration_re.match(value)
        if not match:
            match = mix_duration_re.match(value)
        if not match:
            return parse_duration(value)
        else:
            kw = match.groupdict()
            kw = {k: float(v) for k, v in kw.items() if v is not None}
            return datetime.timedelta(**kw)

class DurationField(forms.DurationField):
    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime.timedelta):
            return value
        value = parse_duration_ext(value)
        if value is None:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return value
            
