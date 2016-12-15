# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns
from django.views.generic import RedirectView

urlpatterns = patterns('',
     (r'^wg/$', 'ietf.mailinglists.views.groups'),
     (r'^nonwg/$', RedirectView.as_view(url='https://www.ietf.org/list/nonwg.html', permanent=True)),
     (r'^nonwg/update/$', RedirectView.as_view(url='https://www.ietf.org/list/nonwg.html', permanent=True)),
     (r'^request/$', RedirectView.as_view(url='https://www.ietf.org/list/request.html', permanent=True)),
)
