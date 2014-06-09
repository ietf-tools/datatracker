# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns

urlpatterns = patterns('',
    (r'^(?P<acronym>[a-z0-9]+).json$', 'ietf.group.ajax.group_json'),
    (r'^chartering/$', 'ietf.group.info.chartering_groups'),
    (r'^chartering/create/(?P<group_type>(wg|rg))/$', 'ietf.group.edit.edit', {'action': "charter"}, "group_create"),
    (r'^concluded/$', 'ietf.group.info.concluded_groups'),
)


