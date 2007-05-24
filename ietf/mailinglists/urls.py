from django.conf.urls.defaults import *
from ietf.idtracker.models import Areas
from ietf.mailinglists import views
from ietf.mailinglists.models import NonWgMailingList
from ietf.mailinglists.forms import NonWgStep1

urlpatterns = patterns('django.views.generic.list_detail',
     (r'^area_lists/$', 'object_list', { 'queryset': Areas.objects.filter(status=1).select_related().order_by('acronym.acronym'), 'template_name': 'mailinglists/areas_list.html' }),
     (r'^nonwg_lists/$', 'object_list', { 'queryset': NonWgMailingList.objects.filter(status__gt=0) }),
)
urlpatterns += patterns('',
     (r'^nonwg_lists/submit/$', views.non_wg_wizard),
     (r'^request/$', views.list_req_wizard),
)
