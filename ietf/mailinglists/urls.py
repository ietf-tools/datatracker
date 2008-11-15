# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.idtracker.models import Area
from ietf.mailinglists import views
from ietf.mailinglists.models import NonWgMailingList
#from ietf.mailinglists.forms import NonWgStep1

urlpatterns = patterns('django.views.generic.list_detail',
     (r'^area/$', 'object_list', { 'queryset': Area.objects.filter(status=1).select_related().order_by('acronym.acronym'), 'template_name': 'mailinglists/areas_list.html' }),
     (r'^nonwg/$', 'object_list', { 'queryset': NonWgMailingList.objects.filter(status__gt=0) }),
)
urlpatterns += patterns('',
     (r'^nonwg/update/$', views.non_wg_wizard),
     (r'^request/$', views.list_req_wizard),
     (r'^help/(?P<field>[^/]+)/$', views.list_req_help),
     (r'^approve/(?P<object_id>[^/]+)/$', views.list_approve),
     (r'^wg/$', views.list_wgwebmail),
)
