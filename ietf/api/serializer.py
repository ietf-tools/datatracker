# Copyright The IETF Trust 2018-2024, All Rights Reserved
# -*- coding: utf-8 -*-
"""Serialization utilities

This is _not_ for django-rest-framework!
"""

import hashlib
import json

from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, FieldError
from django.core.serializers.json import Serializer
from django.http import HttpResponse
from django.utils.encoding import smart_str
from django.db.models import Field
from django.db.models.signals import post_save, post_delete, m2m_changed

from django_stubs_ext import QuerySetAny

import debug                            # pyflakes:ignore


def filter_from_queryargs(request):
    #@debug.trace
    def fix_ranges(d):
        for k,v in d.items():
            if v.startswith("[") and v.endswith("]"):
                d[k] = [ s for s in v[1:-1].split(",") if s ]
            elif "," in v:
                d[k] = [ s for s in v.split(",") if s ]
            if k.endswith('__in') and not isinstance(d[k], list):
                d[k] = [ d[k] ]
        return d
    def is_ascii(s):
        return all(ord(c) < 128 for c in s)
    # limit parameter keys to ascii.
    params = dict( (k,v) for (k,v) in list(request.GET.items()) if is_ascii(k) )
    filter = fix_ranges(dict([(k,params[k]) for k in list(params.keys()) if not k.startswith("not__")]))
    exclude = fix_ranges(dict([(k[5:],params[k]) for k in list(params.keys()) if k.startswith("not__")]))
    return filter, exclude

def unique_obj_name(obj):
    """Return a unique string representation for an object, based on app, class and ID
    """
    app = obj._meta.app_label
    model = obj.__class__.__name__.lower()
    id = obj.pk
    return "%s.%s[%s]" % (app,model,id)

def cached_get(key, calculate_value, timeout=None):
    """Try to get value from cache using key. If no value exists calculate
    it by calling calculate_value. Timeout is defined in seconds."""
    value = cache.get(key)
    if value is None:
        value = calculate_value()
        cache.set(key, value, timeout)
    return value

def model_top_level_cache_key(model):
    return model.__module__ + '.' + model._meta.model.__name__

def clear_top_level_cache(sender, instance, *args, **kwargs):
    cache.delete(model_top_level_cache_key(instance))

def clear_top_level_cache_m2m(sender, instance, action, reverse, model, *args, **kwargs):
    # Purge cache for both models affected and the potentially custom 'through' model
    cache.delete_many((
        model_top_level_cache_key(instance),
        model_top_level_cache_key(model),
        model_top_level_cache_key(sender),
    ))

post_save.connect(clear_top_level_cache, dispatch_uid='clear_top_level_cache')
post_delete.connect(clear_top_level_cache, dispatch_uid='clear_top_level_cache')
m2m_changed.connect(clear_top_level_cache_m2m, dispatch_uid='clear_top_level_cache')

class AdminJsonSerializer(Serializer):
    """
    Serializes a QuerySet to Json, with selectable object expansion.
    The representation is different from that of the builtin Json
    serializer in that there is no separate "model", "pk" and "fields"
    entries for each object, instead only the "fields" dictionary is
    serialized, and the model is the key of a top-level dictionary
    entry which encloses the table serialization:
    {
        "app.model": {
            "1": {
                "foo": "1",
                "bar": 42,
            }
        }
    }
    """

    internal_use_only = False
    use_natural_keys = False

    def serialize(self, queryset, **options):
        qi = options.get('query_info', '').encode('utf-8')
        if len(list(queryset)) == 1:
            obj = queryset[0]
            key = 'json:%s:%s' % (hashlib.md5(qi).hexdigest(), unique_obj_name(obj))
            is_cached = cache.get(model_top_level_cache_key(obj)) is True
            if is_cached:
                value = cached_get(key, lambda: super(AdminJsonSerializer, self).serialize(queryset, **options))
            else:
               value = super(AdminJsonSerializer, self).serialize(queryset, **options)
               cache.set(key, value)
               cache.set(model_top_level_cache_key(obj), True)
            return value
        else:
            return super(AdminJsonSerializer, self).serialize(queryset, **options)

    def start_serialization(self):
        super(AdminJsonSerializer, self).start_serialization()
        self.json_kwargs.pop("expand", None)
        self.json_kwargs.pop("query_info", None)

    def get_dump_object(self, obj):
        return self._current

    def end_object(self, obj):
        expansions = [ n.split("__")[0] for n in self.options.get('expand', []) if n ]
        for name in expansions:
            try:
                field = getattr(obj, name)
                #self._current["_"+name] = smart_str(field)
                if not isinstance(field, Field):
                    options = self.options.copy()
                    options["expand"] = [ v[len(name)+2:] for v in options["expand"] if v.startswith(name+"__") ]
                    if hasattr(field, "all"):
                        if options["expand"]:
                            # If the following code (doing qs.select_related() is commented out it
                            # is because it has the unfortunate side effect of changing the json
                            # rendering of booleans, from 'true/false' to '1/0', but only for the
                            # models pulled in by select_related().  If that's acceptable, we can
                            # comment this in again later.  (The problem is known, captured in
                            # Django issue #15040: https://code.djangoproject.com/ticket/15040
                            self._current[name] = dict([ (rel.pk, self.expand_related(rel, name)) for rel in field.all().select_related() ])
                            # self._current[name] = dict([ (rel.pk, self.expand_related(rel, name)) for rel in field.all() ])
                        else:
                            self._current[name] = dict([ (rel.pk, self.expand_related(rel, name)) for rel in field.all() ])
                    else:
                        if callable(field):
                            try:
                                field_value = field()
                            except Exception:
                                field_value = None
                        else:
                            field_value = field
                        if isinstance(field_value, QuerySetAny) or isinstance(field_value, list):
                            self._current[name] = dict([ (rel.pk, self.expand_related(rel, name)) for rel in field_value ])
                        else:
                            if hasattr(field_value, "_meta"):
                                self._current[name] = self.expand_related(field_value, name)
                            else:
                                self._current[name] = str(field_value)
            except ObjectDoesNotExist:
                pass
            except AttributeError:
                names = [f.name for f in obj._meta.get_fields()]
                if name in names and hasattr(obj, '%s_set' % name):
                    related_objects = getattr(obj, '%s_set' % name).all()
                    if self.options["expand"]:
                        self._current[name] = dict([(rel.pk, self.expand_related(rel, name)) for rel in related_objects.select_related()])
                    else:
                        self._current[name] = dict([(rel.pk, self.expand_related(rel, name)) for rel in related_objects])
                else:
                    raise FieldError("Cannot resolve keyword '%s' into field. "
                        "Choices are: %s" % (name, ", ".join(names)))
        super(AdminJsonSerializer, self).end_object(obj)

    def expand_related(self, related, name):
        options = self.options.copy()
        options["expand"] = [ v[len(name)+2:] for v in options["expand"] if v.startswith(name+"__") ]
        bytes = self.__class__().serialize([ related ], **options)
        data = json.loads(bytes)[0]
        if 'password' in data:
            del data['password']
        return data

    def handle_fk_field(self, obj, field):
        try:
            related = getattr(obj, field.name)
        except ObjectDoesNotExist:
            related = None
        if related is not None:
            if field.name in self.options.get('expand', []):
                related = self.expand_related(related, field.name)
            elif self.use_natural_keys and hasattr(related, 'natural_key'):
                related = related.natural_key()
            elif field.remote_field.field_name == related._meta.pk.name:
                # Related to remote object via primary key
                related = smart_str(related._get_pk_val(), strings_only=True)
            else:
                # Related to remote object via other field
                related = smart_str(getattr(related, field.remote_field.field_name), strings_only=True)
        self._current[field.name] = related

    def handle_m2m_field(self, obj, field):
        if field.remote_field.through._meta.auto_created:
            if field.name in self.options.get('expand', []):
                m2m_value = lambda value: self.expand_related(value, field.name)
            elif self.use_natural_keys and hasattr(field.remote_field.to, 'natural_key'):
                m2m_value = lambda value: value.natural_key()
            else:
                m2m_value = lambda value: smart_str(value._get_pk_val(), strings_only=True)
            self._current[field.name] = [m2m_value(related)
                               for related in getattr(obj, field.name).iterator()]

class JsonExportMixin(object):
    """
    Adds JSON export to a DetailView
    """

#     def json_object(self, request, object_id, extra_context=None):
#         "The json view for an object of this model."
#         try:
#             obj = self.get_queryset().get(pk=unquote(object_id))
#         except self.model.DoesNotExist:
#             # Don't raise Http404 just yet, because we haven't checked
#             # permissions yet. We don't want an unauthenticated user to be able
#             # to determine whether a given object exists.
#             obj = None
# 
#         if obj is None:
#             raise Http404(_('%(name)s object with primary key %(key)r does not exist.') % {'name': force_str(self.model._meta.verbose_name), 'key': escape(object_id)})
# 
#         content_type = 'application/json'
#         return HttpResponse(serialize([ obj ], sort_keys=True, indent=3)[2:-2], content_type=content_type)

    def json_view(self, request, filter=None, expand=None):
        if expand is None:
            expand = []
        if filter is None:
            filter = {}
        qfilter, exclude = filter_from_queryargs(request)
        for k in list(qfilter.keys()):
            if k.startswith("_"):
                del qfilter[k]
        # discard a possible apikey, rather than using it as a queryset argument
        if 'apikey' in qfilter:
            del qfilter['apikey']
        qfilter.update(filter)
        filter = qfilter
        key = request.GET.get("_key", "pk")
        exp = [ e for e in request.GET.get("_expand", "").split(",") if e ]
        for e in exp:
            while True:
                expand.append(e)
                if not "__" in e:
                    break
                e = e.rsplit("__", 1)[0]
        #
        expand = set(expand)
        content_type = 'application/json'
        query_info = "%s?%s" % (request.META["PATH_INFO"], request.META["QUERY_STRING"])
        try:
            qs = self.get_queryset().filter(**filter).exclude(**exclude)
        except (FieldError, ValueError) as e:
            return HttpResponse(json.dumps({"error": str(e)}, sort_keys=True, indent=3), content_type=content_type)
        try:
            if expand:
                qs = qs.select_related()
            serializer = AdminJsonSerializer()
            items = [(getattr(o, key), serializer.serialize([o], expand=expand, query_info=query_info) )  for o in qs ]
            qd = dict( ( k, json.loads(v)[0] )  for k,v in items )
        except (FieldError, ValueError) as e:
            return HttpResponse(json.dumps({"error": str(e)}, sort_keys=True, indent=3), content_type=content_type)
        text = json.dumps({smart_str(self.model._meta): qd}, sort_keys=True, indent=3)
        return HttpResponse(text, content_type=content_type)
        
