# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns, url
from django.views.generic import RedirectView, TemplateView

urlpatterns = patterns('',
     (r'^help/$', TemplateView.as_view(template_name='liaisons/help.html')),
     url(r'^help/fields/$', TemplateView.as_view(template_name='liaisons/field_help.html'), name="liaisons_field_help"),
     (r'^help/from_ietf/$', TemplateView.as_view(template_name='liaisons/guide_from_ietf.html')),
     (r'^help/to_ietf/$', TemplateView.as_view(template_name='liaisons/guide_to_ietf.html')),
     (r'^managers/$', RedirectView.as_view(url='http://www.ietf.org/liaison/managers.html')),
)

urlpatterns += patterns('ietf.liaisons.views',
     url(r'^$', 'liaison_list', name='liaison_list'),
     url(r'^(?P<object_id>\d+)/$', 'liaison_detail', name='liaison_detail'),
     url(r'^(?P<object_id>\d+)/edit/$', 'liaison_edit', name='liaison_edit'),
     url(r'^for_approval/$', 'liaison_approval_list', name='liaison_approval_list'),
     url(r'^for_approval/(?P<object_id>\d+)/$', 'liaison_approval_detail', name='liaison_approval_detail'),
     url(r'^add/$', 'add_liaison', name='add_liaison'),
     url(r'^ajax/get_info/$', 'ajax_get_liaison_info'),
     url(r'^ajax/select2search/$', 'ajax_select2_search_liaison_statements', name='ajax_select2_search_liaison_statements'),
)
