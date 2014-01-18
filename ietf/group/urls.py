# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns, url

urlpatterns = patterns('',
    (r'^(?P<acronym>[a-z0-9]+).json$', 'ietf.group.ajax.group_json'),
)


