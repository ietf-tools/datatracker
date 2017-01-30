# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import url, include
from django.conf import settings

urlpatterns = [
    url(r'^$', 'ietf.group.views.active_groups'), 
    url(r'^groupmenu.json', 'ietf.group.views_ajax.group_menu_data', None, "group_menu_data"),
    url(r'^%(acronym)s.json$' % settings.URL_REGEXPS, 'ietf.group.views_ajax.group_json'),
    url(r'^chartering/$', 'ietf.group.views.chartering_groups'),
    url(r'^chartering/create/(?P<group_type>(wg|rg))/$', 'ietf.group.views_edit.edit', {'action': "charter"}, "group_create"),
    url(r'^concluded/$', 'ietf.group.views.concluded_groups'),
    url(r'^email-aliases/$', 'ietf.group.views.email_aliases'),
    url(r'^all-status/$', 'ietf.group.views.all_status'),

    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, 'ietf.group.views.group_home', None, "group_home"),
    url(r'^%(acronym)s/' % settings.URL_REGEXPS, include('ietf.group.urls_info_details')),
]
