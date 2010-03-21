# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.idtracker.models import IDState, IDSubState
from ietf.idtracker import views
from django.views.generic.simple import redirect_to

urlpatterns = patterns('django.views.generic.simple',
     (r'^help/state/$', 'direct_to_template', { 'template': 'idtracker/states.html', 'extra_context': { 'states': IDState.objects.all(), 'substates': IDSubState.objects.all() } }),
     (r'^help/evaluation/$', redirect_to, {'url':'http://www.ietf.org/iesg/voting-procedures.html' }),
)
urlpatterns += patterns('',
     (r'^status/$', views.status),
     (r'^status/last-call/$', views.last_call),
)
urlpatterns += patterns('',
     (r'^rfc0*(?P<rfc_number>\d+)/$', views.redirect_rfc),
     (r'^(?P<object_id>\d+)/$', views.redirect_id),
     (r'^(?P<filename>[^/]+)/$', views.redirect_filename),
     (r'^comment/(?P<object_id>\d+)/$', views.redirect_comment),
     (r'^ballot/(?P<object_id>\d+)/$', views.redirect_ballot),
     (r'^([^/]+)/comment/(?P<object_id>\d+)/$', views.redirect_comment),
     (r'^help/state/(?P<state>\d+)/$', views.state_desc),
     (r'^help/substate/(?P<state>\d+)/$', views.state_desc, { 'is_substate': 1 }),
     (r'^$', redirect_to, { 'url': '/doc/'}),
)
