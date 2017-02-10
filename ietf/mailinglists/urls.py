# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import url
from django.views.generic import RedirectView

from ietf.mailinglists import views

urlpatterns = [
    url(r'^wg/$', views.groups),
    url(r'^nonwg/$', RedirectView.as_view(url='https://www.ietf.org/list/nonwg.html', permanent=True)),
    url(r'^nonwg/update/$', RedirectView.as_view(url='https://www.ietf.org/list/nonwg.html', permanent=True)),
    url(r'^request/$', RedirectView.as_view(url='https://www.ietf.org/list/request.html', permanent=True)),
]
