# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns, url
from django.views.generic import RedirectView, TemplateView

urlpatterns = patterns('',
    (r'^help/$', TemplateView.as_view(template_name='liaisons/help.html')),
    url(r'^help/fields/$', TemplateView.as_view(template_name='liaisons/field_help.html'), name='liaisons_field_help'),
    (r'^help/from_ietf/$', TemplateView.as_view(template_name='liaisons/guide_from_ietf.html')),
    (r'^help/to_ietf/$', TemplateView.as_view(template_name='liaisons/guide_to_ietf.html')),
    (r'^managers/$', RedirectView.as_view(url='https://www.ietf.org/liaison/managers.html')),
)

# AJAX views
urlpatterns += patterns('ietf.liaisons.views',
    (r'^ajax/get_info/$', 'ajax_get_liaison_info'),
    (r'^ajax/select2search/$', 'ajax_select2_search_liaison_statements'),
)

# Views
urlpatterns += patterns('ietf.liaisons.views',
    (r'^$', 'liaison_list'),
    (r'^(?P<state>(posted|pending|dead))/', 'liaison_list'),
    (r'^(?P<object_id>\d+)/$', 'liaison_detail'),
    (r'^(?P<object_id>\d+)/addcomment/$', 'add_comment'),
    (r'^(?P<object_id>\d+)/edit/$', 'liaison_edit'),
    (r'^(?P<object_id>\d+)/edit-attachment/(?P<doc_id>[A-Za-z0-9._+-]+)$', 'liaison_edit_attachment'),
    (r'^(?P<object_id>\d+)/delete-attachment/(?P<attach_id>[A-Za-z0-9._+-]+)$', 'liaison_delete_attachment'),
    (r'^(?P<object_id>\d+)/history/$', 'liaison_history'),
    (r'^(?P<object_id>\d+)/reply/$', 'liaison_reply'),
    (r'^(?P<object_id>\d+)/resend/$', 'liaison_resend'),
    (r'^add/(?P<type>(incoming|outgoing))/$', 'liaison_add'),

    # Redirects for backwards compatibility
    (r'^add/$', 'redirect_add'),
    (r'^for_approval/$', 'redirect_for_approval'),
    (r'^for_approval/(?P<object_id>\d+)/$', 'redirect_for_approval'),
)
