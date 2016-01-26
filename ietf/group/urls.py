# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns, include

urlpatterns = patterns('',
    (r'^$', 'ietf.group.info.active_groups'), 
    (r'^groupmenu.json', 'ietf.group.ajax.group_menu_data', None, "group_menu_data"),
    (r'^(?P<acronym>[a-z0-9]+).json$', 'ietf.group.ajax.group_json'),
    (r'^chartering/$', 'ietf.group.info.chartering_groups'),
    (r'^chartering/create/(?P<group_type>(wg|rg))/$', 'ietf.group.edit.edit', {'action': "charter"}, "group_create"),
    (r'^concluded/$', 'ietf.group.info.concluded_groups'),
    (r'^email-aliases/$', 'ietf.group.info.email_aliases'),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/$', 'ietf.group.info.group_home', None, "group_home"),
    (r'^(?P<acronym>[a-zA-Z0-9-._]+)/', include('ietf.group.urls_info_details')),
)

