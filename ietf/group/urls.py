# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import url, include
from django.conf import settings

from ietf.group import views, views_ajax, views_edit

urlpatterns = [
    url(r'^$', views.active_groups), 
    url(r'^groupmenu.json', views_ajax.group_menu_data, None, "group_menu_data"),
    url(r'^%(acronym)s.json$' % settings.URL_REGEXPS, views_ajax.group_json),
    url(r'^chartering/$', views.chartering_groups),
    url(r'^chartering/create/(?P<group_type>(wg|rg))/$', views_edit.edit, {'action': "charter"}, "group_create"),
    url(r'^concluded/$', views.concluded_groups),
    url(r'^email-aliases/$', views.email_aliases),
    url(r'^all-status/$', views.all_status),

    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, views.group_home, None, "group_home"),
    url(r'^%(acronym)s/' % settings.URL_REGEXPS, include('ietf.group.urls_info_details')),
]
