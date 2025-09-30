# Copyright The IETF Trust 2025, All Rights Reserved

from django.urls import re_path, include
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView

urlpatterns = [
    re_path(r'^$', TemplateView.as_view(template_name='index.html'), name='ietf.secr'),
    re_path(r'^announcement/', include('ietf.secr.announcement.urls')),
    re_path(r'^meetings/', include('ietf.secr.meetings.urls')),
    re_path(r'^rolodex/', include('ietf.secr.rolodex.urls')),
    re_path(r'^sreq/', RedirectView.as_view(url='/meeting/session/request/', permanent=True)),
    re_path(r'^telechat/', include('ietf.secr.telechat.urls')),
]
