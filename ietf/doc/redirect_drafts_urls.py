# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf import settings
from django.conf.urls.defaults import patterns


from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404

from ietf.group.models import Group

urlpatterns = patterns('',
     (r'^$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/'}),
     (r'^all/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/all/'}),
     (r'^rfc/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/all/#rfc'}),
     (r'^dead/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/all/#expired'}),
     (r'^current/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/active/'}),
     (r'^(?P<object_id>\d+)/(related/)?$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/' }),
     (r'^(?P<name>[^/]+)/(related/)?$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/%(name)s/' }),
     (r'^wgid/(?P<id>\d+)/$', lambda request, id: HttpResponsePermanentRedirect("/wg/%s/" % get_object_or_404(Group, id=id).acronym)),
     (r'^wg/(?P<acronym>[^/]+)/$', 'django.views.generic.simple.redirect_to', { 'url': '/wg/%(acronym)s/' }),
     (r'^all_id(?:_txt)?.html$', 'django.views.generic.simple.redirect_to', { 'url': 'http://www.ietf.org/id/all_id.txt' }),
)
