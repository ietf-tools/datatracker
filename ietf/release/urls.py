# Copyright The IETF Trust 2015-2022, All Rights Reserved
# -*- coding: utf-8 -*-


from django.views.generic import RedirectView, TemplateView

from ietf.utils.urls import url

urlpatterns = [
    url(r'^$',  RedirectView.as_view(url='https://github.com/ietf-tools/datatracker/releases', permanent=False), name='ietf.release.views.release'),
    url(r'^(?P<version>[0-9.]+.*)/$', RedirectView.as_view(url='https://github.com/ietf-tools/datatracker/releases/tag/%(version)s', permanent=False)),
    url(r'^about/?$',  TemplateView.as_view(template_name='release/about.html'), name='releaseabout'),
    url(r'^stats/?$',  RedirectView.as_view(url='https://github.com/ietf-tools/datatracker/releases', permanent=False)),
]
