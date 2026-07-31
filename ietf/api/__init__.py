# Copyright The IETF Trust 2014-2020, All Rights Reserved


import datetime
import re
import sys
from urllib.parse import urlencode

import tastypie.resources
import tastypie.serializers
from django.apps import apps as django_apps
from django.core.exceptions import ObjectDoesNotExist
from django.db import DataError, transaction
from django.http import HttpResponseNotAllowed
from django.utils.module_loading import autodiscover_modules
from tastypie.api import Api
from tastypie.bundle import Bundle
from tastypie.exceptions import ApiFieldError, BadRequest, InvalidFilterError
from tastypie.fields import ApiField

import debug  # noqa: F401  (pyflakes:ignore)
from ietf.utils.log import log

_api_list = []

OMITTED_APPS_APIS = ["ietf.status"]

# Pre-py3.11, fromisoformat() does not handle Z or +HH tz offsets
HAVE_BROKEN_FROMISOFORMAT = sys.version_info < (3, 11, 0, "", 0)


def populate_api_list():
    _module_dict = globals()
    for app_config in django_apps.get_app_configs():
        if "." in app_config.name and app_config.name not in OMITTED_APPS_APIS:
            _root, _name = app_config.name.split(".", 1)
            if _root == "ietf" and "." not in _name:
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
    def dispatch(self, request_type, request, **kwargs):
        """Turn a database error caused by request data into a bad request

        Filter values reach the database with very little validation, and some of
        them only fail once the query actually runs - below tastypie, and long
        after build_filters() had any chance to reject them. Left alone those
        surface as unhandled exceptions.

        Only DataError is treated this way: it is the DBAPI error for a problem
        with the data in the query, so it is the client's to fix. The other
        DatabaseError subclasses (OperationalError, ProgrammingError,
        InternalError) indicate a broken database or a bug of ours, and are left
        alone so they still raise and report.

        The database's message is logged rather than returned - it can quote the
        offending value, and this response body is not escaped.
        """
        try:
            return super().dispatch(request_type, request, **kwargs)
        except DataError as err:
            # The failed statement has aborted the transaction if there is one, so
            # nothing more can be done with the connection until it is rolled back.
            # Requests normally run in autocommit, where there is no transaction to
            # roll back and this is a no-op, but without it the guard would quietly
            # stop working if ATOMIC_REQUESTS were ever turned on: the 400 would be
            # built and then lost when the atomic block failed to commit.
            if not transaction.get_autocommit():
                transaction.set_rollback(True)
            log(f"DataError handling {request.method} {request.get_full_path()}: {err}")
            raise BadRequest(
                "The database could not process this request. This is usually a "
                "malformed filter value."
            )

    def post_detail(self, request, **kwargs):
        return HttpResponseNotAllowed(["GET"])

    def generate_cache_key(self, *args, **kwargs):
        """
        Creates a unique-enough cache key.

        This is based off the current api_name/resource_name/args/kwargs.
        """
        # smooshed = ["%s=%s" % (key, value) for key, value in kwargs.items()]
        smooshed = urlencode(kwargs)

        # Use a list plus a ``.join()`` because it's faster than concatenation.
        return f"{self._meta.api_name}:{self._meta.resource_name}:{':'.join(args)}:{smooshed}"

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
        try:
            py_value = super().filter_value_to_python(
                value, field_name, filters, filter_expr, filter_type
            )
        except TypeError:
            # For "in" and "range" filters tastypie calls len() on the value, but
            # string_to_python() has already mapped "true"/"false"/"nil"/"none" to a
            # bool or None, which have no len().
            raise InvalidFilterError(
                f"Invalid value for the '{filter_type}' filter on '{field_name}'"
            )
        if filter_type == "range" and len(py_value) != 2:
            # Django renders a range lookup as "BETWEEN %s AND %s" and indexes the
            # value without checking its length, so anything other than exactly two
            # values raises IndexError (or ValueError) when the query is compiled -
            # long after this method has returned, where it can only become a 500.
            # Reject it here, while it can still be reported as a bad request.
            raise InvalidFilterError(
                f"The '{filter_type}' filter on '{field_name}' requires exactly two "
                f"comma-separated values"
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


TIMEDELTA_REGEX = re.compile(
    r"^(?P<days>\d+d)?\s?(?P<hours>\d+h)?\s?(?P<minutes>\d+m)?\s?(?P<seconds>\d+s?)$"
)


class TimedeltaField(ApiField):
    dehydrated_type = "timedelta"
    help_text = "A timedelta field, with duration expressed in seconds. Ex: 132"

    def convert(self, value):
        if value is None:
            return None

        if isinstance(value, str):
            match = TIMEDELTA_REGEX.search(value)

            if match:
                data = match.groupdict()
                return datetime.timedelta(
                    int(data["days"]),
                    int(data["hours"]),
                    int(data["minutes"]),
                    int(data["seconds"]),
                )
            else:
                raise ApiFieldError(
                    f"Timedelta provided to '{self.instance_name}' field doesn't appear to be a valid timedelta string: '{value}'"
                )

        return value

    def hydrate(self, bundle):
        value = super().hydrate(bundle)

        if value and not hasattr(value, "seconds"):
            if isinstance(value, str):
                try:
                    match = TIMEDELTA_REGEX.search(value)

                    if match:
                        data = match.groupdict()
                        value = datetime.timedelta(
                            int(data["days"]),
                            int(data["hours"]),
                            int(data["minutes"]),
                            int(data["seconds"]),
                        )
                    else:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise ApiFieldError(
                        f"Timedelta provided to '{self.instance_name}' field doesn't appear to be a valid datetime string: '{value}'"
                    )

            else:
                raise ApiFieldError(
                    f"Datetime provided to '{self.instance_name}' field must be a string: {value}"
                )

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
                    raise ApiFieldError(
                        f"The related resource for resource {previous_obj} could not be found."
                    )
                else:
                    raise ApiFieldError(
                        f"The model '{previous_obj!r}' has an empty attribute '{attrib}' and doesn't allow a null value."
                    )
            return None

        fk_resource = self.get_related_resource(foreign_obj)

        # Up to this point we've copied the code from tastypie 0.13.1.  Now
        # we add caching.
        cache_key = fk_resource.generate_cache_key(
            "related",
            pk=foreign_obj.pk,
            for_list=for_list,
        )
        dehydrated = fk_resource._meta.cache.get(cache_key)
        if dehydrated is None:
            fk_bundle = Bundle(obj=foreign_obj, request=bundle.request)
            dehydrated = self.dehydrate_related(
                fk_bundle, fk_resource, for_list=for_list
            )
            fk_resource._meta.cache.set(cache_key, dehydrated)
        return dehydrated


# XML 1.0 forbids all control characters except tab (#x9), LF (#xA), and CR (#xD).
# Replace each with its Unicode control picture (U+2400 + codepoint) so the
# substitution is lossless and the result is valid XML.
_XML_INVALID_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class Serializer(tastypie.serializers.Serializer):
    OPTION_ESCAPE_XML_INVALID = "datatracker-escape-xml-invalid"

    def format_datetime(self, data):
        return (
            data.astimezone(datetime.UTC)
            .replace(tzinfo=None)
            .isoformat(timespec="seconds")
            + "Z"
        )

    def to_simple(self, data, options):
        options = options or {}
        simple_data = super().to_simple(data, options)
        if options.get(self.OPTION_ESCAPE_XML_INVALID, False) and isinstance(
            simple_data, str
        ):
            # Replace control chars invalid in XML 1.0 with their Unicode
            # control pictures (U+2400-U+241F) so lxml won't reject the string.
            simple_data = _XML_INVALID_CTRL_RE.sub(
                lambda m: chr(ord(m.group()) + 0x2400), simple_data
            )
        return simple_data

    def to_etree(self, data, options=None, name=None, depth=0):
        # lxml rejects control characters that are invalid in XML 1.0.
        # Ask to_simple() to escape them before they reach lxml.
        options = options or {}
        options[self.OPTION_ESCAPE_XML_INVALID] = True
        return super().to_etree(data, options, name, depth)
