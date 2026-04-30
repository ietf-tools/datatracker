# Copyright The IETF Trust 2014-2026, All Rights Reserved


from ietf.api import ModelResource
from tastypie.fields import CharField
from tastypie.constants import ALL
from tastypie.cache import SimpleCache

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from ietf import api
from ietf.utils.models import DirtyBits, DumpInfo


class UserResource(ModelResource):
    username = CharField()
    class Meta:
        cache = SimpleCache()
        queryset = User.objects.all()
        serializer = api.Serializer()


class ContentTypeResource(ModelResource):
    username = CharField()
    class Meta:
        cache = SimpleCache()
        queryset = ContentType.objects.all()
        serializer = api.Serializer()


class DumpInfoResource(ModelResource):
    class Meta:
        cache = SimpleCache()
        queryset = DumpInfo.objects.all()
        serializer = api.Serializer()
        #resource_name = 'dumpinfo'
        ordering = ['id', ]
        filtering = { 
            "date": ALL,
            "host": ALL,
        }
api.utils.register(DumpInfoResource())


class DirtyBitsResource(ModelResource):
    class Meta:
        queryset = DirtyBits.objects.none()
api.utils.register(DirtyBitsResource())
