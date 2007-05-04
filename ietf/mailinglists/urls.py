from django.conf.urls.defaults import *
from ietf.idtracker.models import Areas
from ietf.mailinglists.models import NonWgMailingList

urlpatterns = patterns('django.views.generic.list_detail',
     (r'^area_lists/$', 'object_list', { 'queryset': Areas.objects.filter(status=1).select_related().order_by('acronym.acronym'), 'template_name': 'mailinglists/areas_list.html' }),
     (r'^nonwg_lists/$', 'object_list', { 'queryset': NonWgMailingList.objects.filter(status__gt=0) }),
)
