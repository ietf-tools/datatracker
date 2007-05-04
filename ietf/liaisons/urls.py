from django.conf.urls.defaults import *
from ietf.liaisons.models import LiaisonDetail, LiaisonManagers

info_dict = {
    'queryset': LiaisonDetail.objects.all().order_by("-submitted_date"),
}

# there's an opportunity for date-based filtering.
urlpatterns = patterns('django.views.generic.list_detail',
     (r'^$', 'object_list', info_dict),
     (r'^(?P<object_id>\d+)/$', 'object_detail', info_dict),
     (r'^managers/$', 'object_list', { 'queryset': LiaisonManagers.objects.all().select_related().order_by('sdos.sdo_name') }),	#XXX order_by relies on select_related()
)

urlpatterns += patterns('django.views.generic.simple',
     (r'^help/$', 'direct_to_template', {'template': 'liaisons/help.html'}),
     (r'^help/fields/', 'direct_to_template', {'template': 'liaisons/field_help.html'}),
     (r'^help/from_ietf/', 'direct_to_template', {'template': 'liaisons/guide_from_ietf.html'}),
     (r'^help/to_ietf/', 'direct_to_template', {'template': 'liaisons/guide_to_ietf.html'}),
)
