# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns
from django.views.generic import RedirectView
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404

from ietf.group.models import Group

urlpatterns = patterns('',
     (r'^$', RedirectView.as_view(url='/doc/', permanent=True)),
     (r'^all/$', RedirectView.as_view(url='/doc/all/', permanent=True)),
     (r'^rfc/$', RedirectView.as_view(url='/doc/all/#rfc', permanent=True)),
     (r'^dead/$', RedirectView.as_view(url='/doc/all/#expired', permanent=True)),
     (r'^current/$', RedirectView.as_view(url='/doc/active/', permanent=True)),
     (r'^(?P<object_id>\d+)/(related/)?$', RedirectView.as_view(url='/doc/', permanent=True)),
     (r'^(?P<name>[^/]+)/(related/)?$', RedirectView.as_view(url='/doc/%(name)s/', permanent=True)),
     (r'^wgid/(?P<id>\d+)/$', lambda request, id: HttpResponsePermanentRedirect("/wg/%s/" % get_object_or_404(Group, id=id).acronym)),
     (r'^wg/(?P<acronym>[^/]+)/$', RedirectView.as_view(url='/wg/%(acronym)s/', permanent=True)),
     (r'^all_id(?:_txt)?.html$', RedirectView.as_view(url='https://www.ietf.org/id/all_id.txt', permanent=True)),
)
