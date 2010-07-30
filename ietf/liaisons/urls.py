# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns, url
from django.db.models import Q
from ietf.liaisons.models import LiaisonDetail

info_dict = {
    'queryset': LiaisonDetail.objects.filter(Q(approval__isnull=True)|Q(approval__approved=True)).order_by("-submitted_date"),
}

# there's an opportunity for date-based filtering.
urlpatterns = patterns('django.views.generic.list_detail',
     url(r'^$', 'object_list', info_dict, name='liaison_list'),
     url(r'^(?P<object_id>\d+)/$', 'object_detail', info_dict, name='liaison_detail'),
)

urlpatterns += patterns('django.views.generic.simple',
     (r'^help/$', 'direct_to_template', {'template': 'liaisons/help.html'}),
     (r'^help/fields/$', 'direct_to_template', {'template': 'liaisons/field_help.html'}),
     (r'^help/from_ietf/$', 'direct_to_template', {'template': 'liaisons/guide_from_ietf.html'}),
     (r'^help/to_ietf/$', 'direct_to_template', {'template': 'liaisons/guide_to_ietf.html'}),
     (r'^managers/$', 'redirect_to', { 'url': 'http://www.ietf.org/liaison/managers.html' })
)

urlpatterns += patterns('ietf.liaisons.views',
     url(r'^add/$', 'add_liaison', name='add_liaison'),
     url(r'^ajax/get_info/$', 'get_info', name='get_info'),
)
