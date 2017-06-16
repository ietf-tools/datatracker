# Copyright The IETF Trust 2007, All Rights Reserved

from django.views.generic import RedirectView
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404

from ietf.group.models import Group
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', RedirectView.as_view(url='/doc/', permanent=True)),
    url(r'^all/$', RedirectView.as_view(url='/doc/all/', permanent=True)),
    url(r'^rfc/$', RedirectView.as_view(url='/doc/all/#rfc', permanent=True)),
    url(r'^dead/$', RedirectView.as_view(url='/doc/all/#expired', permanent=True)),
    url(r'^current/$', RedirectView.as_view(url='/doc/active/', permanent=True)),
    url(r'^(?P<object_id>\d+)/(related/)?$', RedirectView.as_view(url='/doc/', permanent=True)),
    url(r'^(?P<name>[^/]+)/(related/)?$', RedirectView.as_view(url='/doc/%(name)s/', permanent=True)),
    url(r'^wgid/(?P<id>\d+)/$', lambda request, id: HttpResponsePermanentRedirect("/wg/%s/" % get_object_or_404(Group, id=id).acronym)),
    url(r'^wg/(?P<acronym>[^/]+)/$', RedirectView.as_view(url='/wg/%(acronym)s/', permanent=True)),
    url(r'^all_id(?:_txt)?.html$', RedirectView.as_view(url='https://www.ietf.org/id/all_id.txt', permanent=True)),
]
