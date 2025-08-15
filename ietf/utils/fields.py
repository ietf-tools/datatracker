# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import json
import re

import debug                            # pyflakes:ignore

from typing import Optional, Type # pyflakes:ignore

from django import forms
from django.db import models # pyflakes:ignore
from django.core.validators import ProhibitNullCharactersValidator, validate_email
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


class DatepickerMedia:
    """Media definitions needed for Datepicker widgets"""
    css = dict(all=('ietf/css/datepicker.css',))
    js = ('ietf/js/datepicker.js',)


class DatepickerDateInput(forms.DateInput):
    """DateInput that uses the Bootstrap datepicker

    The format must be in the Bootstrap datepicker format (yyyy-mm-dd, e.g.), not the
    strftime format. The picker_settings argument is a dict of parameters for the datepicker,
    converting their camelCase names to dash-separated lowercase names and omitting the
    'data-date' prefix to the key.
    """
    Media = DatepickerMedia

    def __init__(self, attrs=None, date_format=None, picker_settings=None):
        super().__init__(
            attrs,
            yyyymmdd_to_strftime_format(date_format),
        )
        self.attrs.setdefault('data-provide', 'datepicker')
        self.attrs.setdefault('data-date-format', date_format)
        self.attrs.setdefault("data-date-autoclose", "1")
        self.attrs.setdefault('placeholder', date_format)
        if picker_settings is not None:
            for k, v in picker_settings.items():
                self.attrs['data-date-{}'.format(k)] = v


class DatepickerSplitDateTimeWidget(forms.SplitDateTimeWidget):
    """Split datetime widget using Bootstrap datepicker

    The format must be in the Bootstrap datepicker format (yyyy-mm-dd, e.g.), not the
    strftime format. The picker_settings argument is a dict of parameters for the datepicker,
    converting their camelCase names to dash-separated lowercase names and omitting the
    'data-date' prefix to the key.
    """
    Media = DatepickerMedia

    def __init__(self, *, date_format='yyyy-mm-dd', picker_settings=None, **kwargs):
        date_attrs = kwargs.setdefault('date_attrs', dict())
        date_attrs.setdefault("data-provide", "datepicker")
        date_attrs.setdefault("data-date-format", date_format)
        date_attrs.setdefault("data-date-autoclose", "1")
        date_attrs.setdefault("placeholder", date_format)
        if picker_settings is not None:
            for k, v in picker_settings.items():
                date_attrs['data-date-{}'.format(k)] = v
        super().__init__(date_format=yyyymmdd_to_strftime_format(date_format), **kwargs)


class DatepickerDateField(forms.DateField):
    """DateField with some glue for triggering JS Bootstrap datepicker"""
    def __init__(self, date_format, picker_settings=None, *args, **kwargs):
        strftime_format = yyyymmdd_to_strftime_format(date_format)
        kwargs["input_formats"] = [strftime_format]
        kwargs["widget"] = DatepickerDateInput(dict(placeholder=date_format), date_format, picker_settings)
        super(DatepickerDateField, self).__init__(*args, **kwargs)


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


class Select2Multiple(forms.SelectMultiple):
    class Media:
        css = {
            'all': (
                'ietf/css/select2.css',
            )
        }
        js = (
            'ietf/js/select2.js',
        )

class SearchableField(forms.MultipleChoiceField):
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
    widget = Select2Multiple
#    model = None  # must be filled in by subclass
    model = None  # type:Optional[Type[models.Model]]
#    max_entries = None  # may be overridden in __init__
    max_entries = None # type: Optional[int]
    min_search_length = None # type: Optional[int]
    default_hint_text = 'Type a value to search'
    
    def __init__(self, hint_text=None, *args, **kwargs):
        assert self.model is not None
        self.hint_text = hint_text if hint_text is not None else self.default_hint_text
        # Pop max_entries out of kwargs - this distinguishes passing 'None' from
        # not setting the parameter at all.
        if 'max_entries' in kwargs:
            self.max_entries = kwargs.pop('max_entries')
        if 'min_search_length' in kwargs:
            self.min_search_length = kwargs.pop('min_search_length')

        super(SearchableField, self).__init__(*args, **kwargs)

        self.widget.attrs["class"] = "select2-field"
        self.widget.attrs["data-placeholder"] = self.hint_text
        if self.max_entries is not None:
            self.widget.attrs["data-max-entries"] = self.max_entries
        if self.min_search_length is not None:
            self.widget.attrs["data-min-search-length"] = self.min_search_length

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

    def prepare_value(self, value):
        if isinstance(value, list):
            if len(value) == 0:
                value = None
            elif len(value) == 1:
                value = value[0]
            else:
                if not isinstance(value[0], self.model):
                    value = self.get_model_instances(value)
        if isinstance(value, int):
            value = str(value)
        if isinstance(value, str):
            if value == "":
                value = self.model.objects.none()
            else:
                value = self.get_model_instances([value])
        if isinstance(value, self.model):
            value = [value]

        pre = self.make_select2_data(value)
        for d in pre:
            if isinstance(value, list):
                d["selected"] = any([v.pk == d["id"] for v in value])
            elif value:
                d["selected"] = value.exists() and value.filter(pk__in=[d["id"]]).exists()
        self.widget.attrs["data-pre"] = json.dumps(list(pre))

        # doing this in the constructor is difficult because the URL
        # patterns may not have been fully constructed there yet
        ajax_url = self.ajax_url()
        if ajax_url is not None:
            self.widget.attrs["data-select2-ajax-url"] = ajax_url

        result = value
        return result

    def clean(self, pks):
        if pks is None:
            return None

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

    def has_changed(self, initial, data):
        # When max_entries == 1, we behave like a ChoiceField so initial will likely be a single
        # value. Make it a list so MultipleChoiceField's has_changed() can work with it.
        if initial is not None and self.max_entries == 1 and not isinstance(initial, (list, tuple)):
            initial = [initial]
        return super().has_changed(initial, data)


class IETFJSONField(forms.JSONField):  # pragma: no cover
    # Deprecated - use EmptyAwareJSONField instead
    def __init__(self, *args, empty_values=forms.JSONField.empty_values,
                 accepted_empty_values=None, **kwargs):
        if accepted_empty_values is None:
            accepted_empty_values = []
        self.empty_values = [x
                             for x in empty_values
                             if x not in accepted_empty_values]

        super().__init__(*args, **kwargs)


class EmptyAwareJSONField(forms.JSONField):
    def __init__(self, *args, empty_values=forms.JSONField.empty_values,
                 accepted_empty_values=None, **kwargs):
        if accepted_empty_values is None:
            accepted_empty_values = []
        self.empty_values = [x
                             for x in empty_values
                             if x not in accepted_empty_values]

        super().__init__(*args, **kwargs)


class MissingOkImageField(models.ImageField):
    """Image field that can validate successfully if file goes missing

    The default ImageField fails even to validate if its back-end file goes
    missing, at least when width_field and height_field are used. This ignores
    the exception that arises. Without this, even deleting a model instance
    through a form fails.
    """
    def update_dimension_fields(self, *args, **kwargs):
        try:
            super().update_dimension_fields(*args, **kwargs)
        except FileNotFoundError:
            pass  # don't do anything if the file has gone missing


class ModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    """ModelMultipleChoiceField that rejects null characters cleanly"""
    validate_no_nulls = ProhibitNullCharactersValidator()

    def clean(self, value):
        try:
            for item in value:
                self.validate_no_nulls(item)
        except TypeError:
            # A TypeError probably means value is not iterable, which most commonly comes up
            # with None as a value. If it's something more exotic, we don't know how to test
            # for null characters anyway. Either way, trust the superclass clean() method to 
            # handle it.
            pass
        return super().clean(value)
