from django.conf.urls.defaults import patterns, url
from django.views.generic.simple import redirect_to

urlpatterns = patterns('',
     (r'^help/(?:sub)?state/(?:\d+/)?$', redirect_to, {'url': '/doc/help/state/draft-iesg/' }),
     (r'^help/evaluation/$', redirect_to, {'url':'http://www.ietf.org/iesg/voting-procedures.html' }),
     (r'^status/$', redirect_to, {'url':'/doc/iesg/' }),
     (r'^status/last-call/$', redirect_to, {'url':'/doc/iesg/last-call/' }),
     (r'^rfc0*(?P<rfc_number>\d+)/$', redirect_to, {'url':'/doc/rfc%(rfc_number)s/' }),
     (r'^(?P<name>[^/]+)/$', redirect_to, {'url':'/doc/%(name)s/' }),
     (r'^(?P<name>[^/]+)/comment/\d+/$', redirect_to, {'url':'/doc/%(name)s/history/' }),
     (r'^$', redirect_to, { 'url': '/doc/'}),
)
