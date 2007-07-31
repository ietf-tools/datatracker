# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.idtracker.models import IDInternal, IDState, IDSubState, DocumentComment, BallotInfo
from ietf.idtracker import views

id_dict = {
    'queryset': IDInternal.objects.all().filter(rfc_flag=0),
}
rfc_dict = {
    'queryset': IDInternal.objects.all().filter(rfc_flag=1),
}
comment_dict = {
    'queryset': DocumentComment.objects.all().filter(public_flag=1),
}

ballot_dict = {
    'queryset': BallotInfo.objects.all()
}

urlpatterns = patterns('django.views.generic.simple',
     (r'^help/state/$', 'direct_to_template', { 'template': 'idtracker/states.html', 'extra_context': { 'states': IDState.objects.all(), 'substates': IDSubState.objects.all() } }),
     (r'^help/ballot/$', 'direct_to_template', { 'template': 'idtracker/view_key.html' }),
     (r'^help/evaluation/$', 'direct_to_template', { 'template': 'idtracker/view_evaluation_desc.html' }),
)
urlpatterns += patterns('',
     (r'^feedback/$', views.send_email),
     (r'^status/$', views.status),
     (r'^status/last-call/$', views.last_call),
)
urlpatterns += patterns('',
     (r'^rfc(?P<object_id>\d+)/$', views.view_rfc),
     (r'^(?P<object_id>\d+)/$', views.redirect_id),
     (r'^(?P<slug>[^/]+)/$', views.view_id, dict(id_dict, slug_field='draft__filename')),
     (r'^comment/(?P<object_id>\d+)/$', views.view_comment, comment_dict),
     (r'^ballot/(?P<object_id>\d+)/$', views.view_ballot, ballot_dict),
     (r'^(?P<slug>[^/]+)/comment/(?P<object_id>\d+)/$', views.comment, comment_dict),
     (r'^help/state/(?P<state>\d+)/$', views.state_desc),
     (r'^help/substate/(?P<state>\d+)/$', views.state_desc, { 'is_substate': 1 }),
     #(r'^(?P<id>\d+)/edit/$', views.edit_idinternal),
     (r'^$', views.search),
)
