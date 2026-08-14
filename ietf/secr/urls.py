# Copyright The IETF Trust 2025, All Rights Reserved

from django.conf import settings
from django.urls import re_path, include
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView

urlpatterns = [
    re_path(r'^$', TemplateView.as_view(template_name='index.html'), name='ietf.secr'),
    re_path(r'^announcement/', include('ietf.secr.announcement.urls')),
    re_path(r'^meetings/', include('ietf.secr.meetings.urls')),
    re_path(r'^rolodex/', include('ietf.secr.rolodex.urls')),
    # remove these redirects after 125
    re_path(r'^sreq/$', RedirectView.as_view(url='/meeting/session/request/', permanent=True)),
    re_path(r'^sreq/%(acronym)s/$' % settings.URL_REGEXPS, RedirectView.as_view(url='/meeting/session/request/%(acronym)s/view/', permanent=True)),
    re_path(r'^sreq/%(acronym)s/edit/$' % settings.URL_REGEXPS, RedirectView.as_view(url='/meeting/session/request/%(acronym)s/edit/', permanent=True)),
    re_path(r'^sreq/%(acronym)s/new/$' % settings.URL_REGEXPS, RedirectView.as_view(url='/meeting/session/request/%(acronym)s/new/', permanent=True)),
    re_path(r'^sreq/(?P<num>[A-Za-z0-9_\-\+]+)/%(acronym)s/view/$' % settings.URL_REGEXPS, RedirectView.as_view(url='/meeting/%(num)s/session/request/%(acronym)s/view/', permanent=True)),
    re_path(r'^sreq/(?P<num>[A-Za-z0-9_\-\+]+)/%(acronym)s/edit/$' % settings.URL_REGEXPS, RedirectView.as_view(url='/meeting/%(num)s/session/request/%(acronym)s/edit/', permanent=True)),
    # ---------------------------------
    re_path(r'^telechat/', include('ietf.secr.telechat.urls')),
]
