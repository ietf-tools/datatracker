# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns, url, include
from django.views.generic.simple import redirect_to
from ietf.group import ajax

urlpatterns = patterns('',
    (r'^(?P<groupname>[a-z0-9]+).json$', ajax.group_json),
)


