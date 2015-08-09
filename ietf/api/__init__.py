import re
import six
import datetime

from django.conf import settings
from django.http import HttpResponse
from django.core.urlresolvers import reverse
from django.utils.encoding import force_text

from tastypie.api import Api
from tastypie.bundle import Bundle
from tastypie.serializers import Serializer as BaseSerializer
from tastypie.exceptions import BadRequest, ApiFieldError
from tastypie.utils.mime import determine_format, build_content_type
from tastypie.utils import is_valid_jsonp_callback_value
from tastypie.fields import ApiField

import debug                            # pyflakes:ignore

_api_list = []

class Serializer(BaseSerializer):
    def to_html(self, data, options=None):
        """
        Reserved for future usage.

        The desire is to provide HTML output of a resource, making an API
        available to a browser. This is on the TODO list but not currently
        implemented.
        """
        from django.template.loader import render_to_string as render

        options = options or {}

        serialized = self.to_simple_html(data, options)
        return render("api/base.html", {"data": serialized})

    def to_simple_html(self, data, options):
        """
        """
        from django.template.loader import render_to_string as render
        #
        if isinstance(data, (list, tuple)):
            return render("api/listitem.html", {"data": [self.to_simple_html(item, options) for item in data]})
        if isinstance(data, dict):
            return render("api/dictitem.html", {"data": dict((key, self.to_simple_html(val, options)) for (key, val) in data.items())})
        elif isinstance(data, Bundle):
            return render("api/dictitem.html", {"data":dict((key, self.to_simple_html(val, options)) for (key, val) in data.data.items())})
        elif hasattr(data, 'dehydrated_type'):
            debug.show('data')
            if getattr(data, 'dehydrated_type', None) == 'related' and data.is_m2m == False:
                return render("api/relitem.html", {"fk": data.fk_resource, "val": self.to_simple_html(data.value, options)})
            elif getattr(data, 'dehydrated_type', None) == 'related' and data.is_m2m == True:
                render("api/listitem.html", {"data": [self.to_simple_html(bundle, options) for bundle in data.m2m_bundles]})
            else:
                return self.to_simple_html(data.value, options)
        elif isinstance(data, datetime.datetime):
            return self.format_datetime(data)
        elif isinstance(data, datetime.date):
            return self.format_date(data)
        elif isinstance(data, datetime.time):
            return self.format_time(data)
        elif isinstance(data, bool):
            return data
        elif isinstance(data, (six.integer_types, float)):
            return data
        elif data is None:
            return None
        elif isinstance(data, basestring) and data.startswith("/api/v1/"):  # XXX Will not work for Python 3
            return render("api/relitem.html", {"fk": data, "val": data.split('/')[-2]})
        else:
            return force_text(data)

for _app in settings.INSTALLED_APPS:
    _module_dict = globals()
    if '.' in _app:
        _root, _name = _app.split('.', 1)
        if _root == 'ietf':
            if not '.' in _name:

                _api = Api(api_name=_name)
                _module_dict[_name] = _api
                _api_list.append((_name, _api))

def top_level(request):
    available_resources = {}

    apitop = reverse('ietf.api.top_level')

    for name in sorted([ name for name, api in _api_list if len(api._registry) > 0 ]):
        available_resources[name] = {
            'list_endpoint': '%s/%s/' % (apitop, name),
        }

    serializer = Serializer()
    desired_format = determine_format(request, serializer)

    options = {}

    if 'text/javascript' in desired_format:
        callback = request.GET.get('callback', 'callback')

        if not is_valid_jsonp_callback_value(callback):
            raise BadRequest('JSONP callback name is invalid.')

        options['callback'] = callback

    serialized = serializer.serialize(available_resources, desired_format, options)
    return HttpResponse(content=serialized, content_type=build_content_type(desired_format))

def autodiscover():
    """
    Auto-discover INSTALLED_APPS resources.py modules and fail silently when
    not present. This forces an import on them to register any admin bits they
    may want.
    """

    from django.conf import settings
    from django.utils.importlib import import_module
    from django.utils.module_loading import module_has_submodule

    for app in settings.INSTALLED_APPS:
        mod = import_module(app)
        # Attempt to import the app's admin module.
        try:
            import_module('%s.resources' % (app, ))
        except:
            # Decide whether to bubble up this error. If the app just
            # doesn't have an admin module, we can ignore the error
            # attempting to import it, otherwise we want it to bubble up.
            if module_has_submodule(mod, "resources"):
                raise

TIMEDELTA_REGEX = re.compile('^(?P<days>\d+d)?\s?(?P<hours>\d+h)?\s?(?P<minutes>\d+m)?\s?(?P<seconds>\d+s?)$')

class TimedeltaField(ApiField):
    dehydrated_type = 'timedelta'
    help_text = "A timedelta field, with duration expressed in seconds. Ex: 132"

    def convert(self, value):
        if value is None:
            return None

        if isinstance(value, six.string_types):
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
            if isinstance(value, six.string_types):
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
    
    
