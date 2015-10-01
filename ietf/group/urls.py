# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns, include
from django.conf import settings

urlpatterns = patterns('',
    (r'^$', 'ietf.group.info.active_groups'), 
    (r'^groupmenu.json', 'ietf.group.ajax.group_menu_data', None, "group_menu_data"),
    (r'^%(acronym)s.json$' % settings.URL_REGEXPS, 'ietf.group.ajax.group_json'),
    (r'^chartering/$', 'ietf.group.info.chartering_groups'),
    (r'^chartering/create/(?P<group_type>(wg|rg))/$', 'ietf.group.edit.edit', {'action': "charter"}, "group_create"),
    (r'^concluded/$', 'ietf.group.info.concluded_groups'),
    (r'^email-aliases/$', 'ietf.group.info.email_aliases'),

    (r'^%(acronym)s/$' % settings.URL_REGEXPS, 'ietf.group.info.group_home', None, "group_home"),
    (r'^%(acronym)s/' % settings.URL_REGEXPS, include('ietf.group.urls_info_details')),
)


