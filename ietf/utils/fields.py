# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import json
import re

import debug                            # pyflakes:ignore

from typing import Optional, Type # pyflakes:ignore

from django import forms
from django.db import models # pyflakes:ignore
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


class SearchableTextInput(forms.TextInput):
    class Media:
        css = {
            'all': (
                'select2/select2.css', 
                'select2-bootstrap-css/select2-bootstrap.min.css',
            )
        }
        js = (
            'select2/select2.min.js', 
            'ietf/js/select2-field.js',
        )

# FIXME: select2 version 4 uses a standard select for the AJAX case -
# switching to that would allow us to derive from the standard
# multi-select machinery in Django instead of the manual CharField
# stuff below

class SearchableField(forms.CharField):
    """Base class for searchable fields

    The field uses a comma-separated list of primary keys in a CharField element as its
    API with some extra attributes used by the Javascript part.
    
    When used in a form, the template rendering that form must include the form's media.
    This is done by putting {{ form.media }} in a header block. If CSS and JS should be
    separated for the template, use {{ form.media.css }} and {{ form.media.js }} instead.
    
    To make a usable subclass, you must fill in the model (either as a class-scoped variable
    or in the __init__() method before calling the superclass __init__()) and define
    the make_select2_data() and ajax_url() methods. You likely want to provide a more
    specific default_hint_text as well.
    """
    widget = SearchableTextInput
#    model = None  # must be filled in by subclass
    model = None  # type:Optional[Type[models.Model]]
#    max_entries = None  # may be overridden in __init__
    max_entries = None # type: Optional[int] 
    default_hint_text = 'Type a value to search'
    
    def __init__(self, hint_text=None, *args, **kwargs):
        assert self.model is not None
        self.hint_text = hint_text if hint_text is not None else self.default_hint_text
        kwargs["max_length"] = 10000
        # Pop max_entries out of kwargs - this distinguishes passing 'None' from
        # not setting the parameter at all.
        if 'max_entries' in kwargs:
            self.max_entries = kwargs.pop('max_entries')

        super(SearchableField, self).__init__(*args, **kwargs)

        self.widget.attrs["class"] = "select2-field form-control"
        self.widget.attrs["data-placeholder"] = self.hint_text
        if self.max_entries is not None:
            self.widget.attrs["data-max-entries"] = self.max_entries

    def make_select2_data(self, model_instances):
        """Get select2 data items
        
        Should return an array of dicts, each with at least 'id' and 'text' keys.
        """
        raise NotImplementedError('Must implement make_select2_data')

    def ajax_url(self):
        """Get the URL for AJAX searches
        
        Doing this in the constructor is difficult because the URL patterns may not have been
        fully constructed there yet.
        """
        raise NotImplementedError('Must implement ajax_url')

    def get_model_instances(self, item_ids):
        """Get model instances corresponding to item identifiers in select2 field value
        
        Default implementation expects identifiers to be model pks. Return value is an iterable.
        """
        return self.model.objects.filter(pk__in=item_ids)

    def validate_pks(self, pks):
        """Validate format of PKs
        
        Base implementation does nothing, but subclasses may override if desired.
        Should raise a forms.ValidationError in case of a failed validation.
        """
        pass

    def describe_failed_pks(self, failed_pks):
        """Format error message to display when non-existent PKs are referenced"""
        return ('Could not recognize the following {model_name}s: {pks}. '
                'You can only input {model_name}s already registered in the Datatracker.'.format(
            pks=', '.join(failed_pks),
            model_name=self.model.__name__.lower())
        )

    def parse_select2_value(self, value):
        """Parse select2 field value into individual item identifiers"""
        return [x.strip() for x in value.split(",") if x.strip()]

    def prepare_value(self, value):
        if not value:
            value = ""
        if isinstance(value, int):
            value = str(value)
        if isinstance(value, str):
            item_ids = self.parse_select2_value(value)
            value = self.get_model_instances(item_ids)
        if isinstance(value, self.model):
            value = [value]

        self.widget.attrs["data-pre"] = json.dumps({
            d['id']: d for d in self.make_select2_data(value)
        })

        # doing this in the constructor is difficult because the URL
        # patterns may not have been fully constructed there yet
        self.widget.attrs["data-ajax-url"] = self.ajax_url()

        return ",".join(str(o.pk) for o in value)

    def clean(self, value):
        value = super(SearchableField, self).clean(value)
        pks = self.parse_select2_value(value)
        self.validate_pks(pks)

        try:
            objs = self.model.objects.filter(pk__in=pks)
        except ValueError as e:
            raise forms.ValidationError('Unexpected field value; {}'.format(e))

        found_pks = [ str(o.pk) for o in objs ]
        failed_pks = [ x for x in pks if x not in found_pks ]
        if failed_pks:
            raise forms.ValidationError(self.describe_failed_pks(failed_pks))

        if self.max_entries != None and len(objs) > self.max_entries:
            raise forms.ValidationError('You can select at most {} {}.'.format(
                self.max_entries,
                'entry' if self.max_entries == 1 else 'entries', 
            ))

        return objs.first() if self.max_entries == 1 else objs
