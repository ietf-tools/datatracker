# Copyright The IETF Trust 2007, All Rights Reserved

from django.views.generic import RedirectView

from ietf.mailinglists import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^wg/?$', views.groups),
    url(r'^nonwg/?$', views.nonwg),
    url(r'^nonwg/update/?$', RedirectView.as_view(url='https://www.ietf.org/list/nonwg.html', permanent=True)),
    url(r'^request/?$', RedirectView.as_view(url='https://www.ietf.org/list/request.html', permanent=True)),
]
