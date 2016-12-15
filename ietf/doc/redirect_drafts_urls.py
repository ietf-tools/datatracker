# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns
from django.views.generic import RedirectView
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404

from ietf.group.models import Group

urlpatterns = patterns('',
     (r'^$', RedirectView.as_view(url='/doc/')),
     (r'^all/$', RedirectView.as_view(url='/doc/all/')),
     (r'^rfc/$', RedirectView.as_view(url='/doc/all/#rfc')),
     (r'^dead/$', RedirectView.as_view(url='/doc/all/#expired')),
     (r'^current/$', RedirectView.as_view(url='/doc/active/')),
     (r'^(?P<object_id>\d+)/(related/)?$', RedirectView.as_view(url='/doc/')),
     (r'^(?P<name>[^/]+)/(related/)?$', RedirectView.as_view(url='/doc/%(name)s/')),
     (r'^wgid/(?P<id>\d+)/$', lambda request, id: HttpResponsePermanentRedirect("/wg/%s/" % get_object_or_404(Group, id=id).acronym)),
     (r'^wg/(?P<acronym>[^/]+)/$', RedirectView.as_view(url='/wg/%(acronym)s/')),
     (r'^all_id(?:_txt)?.html$', RedirectView.as_view(url='https://www.ietf.org/id/all_id.txt')),
)
