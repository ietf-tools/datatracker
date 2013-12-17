# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns

urlpatterns = patterns('',
     (r'^wg/$', 'ietf.mailinglists.views.groups'),
     (r'^nonwg/$', 'django.views.generic.simple.redirect_to', { 'url': 'http://www.ietf.org/list/nonwg.html'}),
     (r'^nonwg/update/$', 'django.views.generic.simple.redirect_to', { 'url': 'http://www.ietf.org/list/nonwg.html'}),
     (r'^request/$', 'django.views.generic.simple.redirect_to', { 'url': 'http://www.ietf.org/list/request.html' }),
)
