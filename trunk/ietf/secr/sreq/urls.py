# Copyright The IETF Trust 2007-2019, All Rights Reserved

from django.conf import settings

from ietf.secr.sreq import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.main),
    url(r'^status/$', views.tool_status),
    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, views.view),
    url(r'^(?P<num>[A-Za-z0-9_\-\+]+)/%(acronym)s/view/$' % settings.URL_REGEXPS, views.view),
    url(r'^%(acronym)s/approve/$' % settings.URL_REGEXPS, views.approve),
    url(r'^%(acronym)s/cancel/$' % settings.URL_REGEXPS, views.cancel),
    url(r'^%(acronym)s/confirm/$' % settings.URL_REGEXPS, views.confirm),
    url(r'^%(acronym)s/edit/$' % settings.URL_REGEXPS, views.edit),
    url(r'^%(acronym)s/new/$' % settings.URL_REGEXPS, views.new),
    url(r'^%(acronym)s/no_session/$' % settings.URL_REGEXPS, views.no_session),
    url(r'^(?P<num>[A-Za-z0-9_\-\+]+)/%(acronym)s/edit/$' % settings.URL_REGEXPS, views.edit),
]
