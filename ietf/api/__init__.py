# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import re
import sys

from urllib.parse import urlencode

from django.apps import apps as django_apps
from django.core.exceptions import ObjectDoesNotExist
from django.utils.module_loading import autodiscover_modules


import debug                            # pyflakes:ignore

import tastypie.resources
import tastypie.serializers
from tastypie.api import Api
from tastypie.bundle import Bundle
from tastypie.exceptions import ApiFieldError
from tastypie.fields import ApiField

_api_list = []

OMITTED_APPS_APIS = ["ietf.status"]

# Pre-py3.11, fromisoformat() does not handle Z or +HH tz offsets
HAVE_BROKEN_FROMISOFORMAT = sys.version_info < (3, 11, 0, "", 0)

def populate_api_list():
    _module_dict = globals()
    for app_config in django_apps.get_app_configs():
        if '.' in app_config.name and app_config.name not in OMITTED_APPS_APIS:
            _root, _name = app_config.name.split('.', 1)
            if _root == 'ietf':
                if not '.' in _name:
                    _api = Api(api_name=_name)
                    _module_dict[_name] = _api
                    _api_list.append((_name, _api))

def autodiscover():
    """
    Auto-discover INSTALLED_APPS resources.py modules and fail silently when
    not present. This forces an import on them to register any resources they
    may want.
    """
    autodiscover_modules("resources")


class ModelResource(tastypie.resources.ModelResource):
    def generate_cache_key(self, *args, **kwargs):
        """
        Creates a unique-enough cache key.

        This is based off the current api_name/resource_name/args/kwargs.
        """
        #smooshed = ["%s=%s" % (key, value) for key, value in kwargs.items()]
        smooshed = urlencode(kwargs)

        # Use a list plus a ``.join()`` because it's faster than concatenation.
        return "%s:%s:%s:%s" % (self._meta.api_name, self._meta.resource_name, ':'.join(args), smooshed)

    def _z_aware_fromisoformat(self, value: str) -> datetime.datetime:
        """datetime.datetime.fromisoformat replacement that works with python < 3.11"""
        if HAVE_BROKEN_FROMISOFORMAT:
            if value.upper().endswith("Z"):
                value = value[:-1] + "+00:00"  # Z -> UTC
            elif re.match(r"[+-][0-9][0-9]$", value[-3:]):
                value = value + ":00"  # -04 -> -04:00
        return datetime.datetime.fromisoformat(value)

    def filter_value_to_python(
        self, value, field_name, filters, filter_expr, filter_type
    ):
        py_value = super().filter_value_to_python(
            value, field_name, filters, filter_expr, filter_type
        )
        if isinstance(
            self.fields[field_name], tastypie.fields.DateTimeField
        ) and isinstance(py_value, str):
            # Ensure datetime values are TZ-aware, using UTC by default
            try:
                dt = self._z_aware_fromisoformat(py_value)
            except ValueError:
                pass  # let tastypie deal with the original value
            else:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                py_value = dt.isoformat()
        return py_value


TIMEDELTA_REGEX = re.compile(r'^(?P<days>\d+d)?\s?(?P<hours>\d+h)?\s?(?P<minutes>\d+m)?\s?(?P<seconds>\d+s?)$')

class TimedeltaField(ApiField):
    dehydrated_type = 'timedelta'
    help_text = "A timedelta field, with duration expressed in seconds. Ex: 132"

    def convert(self, value):
        if value is None:
            return None

        if isinstance(value, str):
            match = TIMEDELTA_REGEX.search(value)

            if match:
                data = match.groupdict()
                return datetime.timedelta(int(data['days']), int(data['hours']), int(data['minutes']), int(data['seconds']))
            else:
                raise ApiFieldError("Timedelta provided to '%s' field doesn't appear to be a valid timedelta string: '%s'" % (self.instance_name, value))

        return value

    def hydrate(self, bundle):
        value = super(TimedeltaField, self).hydrate(bundle)

        if value and not hasattr(value, 'seconds'):
            if isinstance(value, str):
                try:
                    match = TIMEDELTA_REGEX.search(value)

                    if match:
                        data = match.groupdict()
                        value = datetime.timedelta(int(data['days']), int(data['hours']), int(data['minutes']), int(data['seconds']))
                    else:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise ApiFieldError("Timedelta provided to '%s' field doesn't appear to be a valid datetime string: '%s'" % (self.instance_name, value))

            else:
                raise ApiFieldError("Datetime provided to '%s' field must be a string: %s" % (self.instance_name, value))

        return value

class ToOneField(tastypie.fields.ToOneField):
    "Subclass of tastypie.fields.ToOneField which adds caching in the dehydrate method."

    def dehydrate(self, bundle, for_list=True):
        foreign_obj = None
        previous_obj = None
        attrib = None
        
        if callable(self.attribute):
            previous_obj = bundle.obj
            foreign_obj = self.attribute(bundle)
        elif isinstance(self.attribute, str):
            foreign_obj = bundle.obj

            for attr in self._attrs:
                attrib = attr
                previous_obj = foreign_obj
                try:
                    foreign_obj = getattr(foreign_obj, attr, None)
                except ObjectDoesNotExist:
                    foreign_obj = None

        if not foreign_obj:
            if not self.null:
                if callable(self.attribute):
                    raise ApiFieldError("The related resource for resource %s could not be found." % (previous_obj))
                else:
                    raise ApiFieldError("The model '%r' has an empty attribute '%s' and doesn't allow a null value." % (previous_obj, attrib))
            return None

        fk_resource = self.get_related_resource(foreign_obj)

        # Up to this point we've copied the code from tastypie 0.13.1.  Now
        # we add caching.
        cache_key = fk_resource.generate_cache_key('related', pk=foreign_obj.pk, for_list=for_list, )
        dehydrated = fk_resource._meta.cache.get(cache_key)
        if dehydrated is None:
            fk_bundle = Bundle(obj=foreign_obj, request=bundle.request)
            dehydrated = self.dehydrate_related(fk_bundle, fk_resource, for_list=for_list)
            fk_resource._meta.cache.set(cache_key, dehydrated)
        return dehydrated


class Serializer(tastypie.serializers.Serializer):
    OPTION_ESCAPE_NULLS = "datatracker-escape-nulls"

    def format_datetime(self, data):
        return data.astimezone(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"

    def to_simple(self, data, options):
        options = options or {}
        simple_data = super().to_simple(data, options)
        if (
            options.get(self.OPTION_ESCAPE_NULLS, False) 
            and isinstance(simple_data, str)
        ):
            # replace nulls with unicode "symbol for null character", \u2400
            simple_data = simple_data.replace("\x00", "\u2400")
        return simple_data

    def to_etree(self, data, options=None, name=None, depth=0):
        # lxml does not escape nulls on its own, so ask to_simple() to do it.
        # This is mostly (only?) an issue when generating errors responses for
        # fuzzers.
        options = options or {}
        options[self.OPTION_ESCAPE_NULLS] = True
        return super().to_etree(data, options, name, depth)
