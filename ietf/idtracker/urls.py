from django.conf.urls.defaults import *
from ietf.idtracker.models import InternetDraft, IDState, IDSubState, DocumentComment
from ietf.idtracker import views

id_dict = {
    'queryset': InternetDraft.objects.all(),
}
comment_dict = {
    'queryset': DocumentComment.objects.all().filter(public_flag=1),
}

urlpatterns = patterns('django.views.generic.simple',
     (r'^states/$', 'direct_to_template', { 'template': 'idtracker/states.html', 'extra_context': { 'states': IDState.objects.all(), 'substates': IDSubState.objects.all() } }),
)
urlpatterns += patterns('django.views.generic.list_detail',
     (r'^(?P<object_id>\d+)/$', 'object_detail', id_dict),
     (r'^(?P<slug>[^/]+)/$', 'object_detail', dict(id_dict, slug_field='filename')),
     (r'^comment/(?P<object_id>\d+)/$', 'object_detail', comment_dict),
)
urlpatterns += patterns('',
     (r'^(?P<slug>[^/]+)/comment/(?P<object_id>\d+)/$', views.comment, comment_dict),
     (r'^states/(?P<state>\d+)/$', views.state_desc),
     (r'^states/substate/(?P<state>\d+)/$', views.state_desc, { 'is_substate': 1 }),
     (r'^(?P<id>\d+)/edit/$', views.edit_idinternal),
     (r'^$', views.search),
)
