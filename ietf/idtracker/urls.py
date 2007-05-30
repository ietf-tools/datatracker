from django.conf.urls.defaults import *
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
     (r'^states/$', 'direct_to_template', { 'template': 'idtracker/states.html', 'extra_context': { 'states': IDState.objects.all(), 'substates': IDSubState.objects.all() } }),
     (r'^ballot_key/$', 'direct_to_template', { 'template': 'idtracker/view_key.html' }),
     (r'^evaluation_process/$', 'direct_to_template', { 'template': 'idtracker/view_evaluation_desc.html' }),
)
urlpatterns += patterns('',
     (r'^send_email/$', views.send_email),
)
urlpatterns += patterns('django.views.generic.list_detail',
     (r'^rfc(?P<object_id>\d+)/$', 'object_detail', rfc_dict),
     (r'^(?P<object_id>\d+)/$', 'object_detail', id_dict),
     (r'^(?P<slug>[^/]+)/$', 'object_detail', dict(id_dict, slug_field='draft__filename')),
     (r'^comment/(?P<object_id>\d+)/$', 'object_detail', comment_dict),
     (r'^ballot/(?P<object_id>\d+)/$', 'object_detail', ballot_dict),
)
urlpatterns += patterns('',
     (r'^(?P<slug>[^/]+)/comment/(?P<object_id>\d+)/$', views.comment, comment_dict),
     (r'^states/(?P<state>\d+)/$', views.state_desc),
     (r'^states/substate/(?P<state>\d+)/$', views.state_desc, { 'is_substate': 1 }),
     (r'^(?P<id>\d+)/edit/$', views.edit_idinternal),
     (r'^$', views.search),
)
