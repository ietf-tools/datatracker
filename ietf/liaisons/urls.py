# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import url
from django.views.generic import RedirectView, TemplateView

urlpatterns = [
    url(r'^help/$', TemplateView.as_view(template_name='liaisons/help.html')),
    url(r'^help/fields/$', TemplateView.as_view(template_name='liaisons/field_help.html'), name='liaisons_field_help'),
    url(r'^help/from_ietf/$', TemplateView.as_view(template_name='liaisons/guide_from_ietf.html')),
    url(r'^help/to_ietf/$', TemplateView.as_view(template_name='liaisons/guide_to_ietf.html')),
    url(r'^managers/$', RedirectView.as_view(url='https://www.ietf.org/liaison/managers.html', permanent=True)),
]

# AJAX views
urlpatterns += [ 
    url(r'^ajax/get_info/$', 'ietf.liaisons.views.ajax_get_liaison_info'),
    url(r'^ajax/select2search/$', 'ietf.liaisons.views.ajax_select2_search_liaison_statements'),
]

# Views
urlpatterns += [ 
    url(r'^$', 'ietf.liaisons.views.liaison_list'),
    url(r'^(?P<state>(posted|pending|dead))/', 'ietf.liaisons.views.liaison_list'),
    url(r'^(?P<object_id>\d+)/$', 'ietf.liaisons.views.liaison_detail'),
    url(r'^(?P<object_id>\d+)/addcomment/$', 'ietf.liaisons.views.add_comment'),
    url(r'^(?P<object_id>\d+)/edit/$', 'ietf.liaisons.views.liaison_edit'),
    url(r'^(?P<object_id>\d+)/edit-attachment/(?P<doc_id>[A-Za-z0-9._+-]+)$', 'ietf.liaisons.views.liaison_edit_attachment'),
    url(r'^(?P<object_id>\d+)/delete-attachment/(?P<attach_id>[A-Za-z0-9._+-]+)$', 'ietf.liaisons.views.liaison_delete_attachment'),
    url(r'^(?P<object_id>\d+)/history/$', 'ietf.liaisons.views.liaison_history'),
    url(r'^(?P<object_id>\d+)/reply/$', 'ietf.liaisons.views.liaison_reply'),
    url(r'^(?P<object_id>\d+)/resend/$', 'ietf.liaisons.views.liaison_resend'),
    url(r'^add/(?P<type>(incoming|outgoing))/$', 'ietf.liaisons.views.liaison_add'),

    # Redirects for backwards compatibility
    url(r'^add/$', 'ietf.liaisons.views.redirect_add'),
    url(r'^for_approval/$', 'ietf.liaisons.views.redirect_for_approval'),
    url(r'^for_approval/(?P<object_id>\d+)/$', 'ietf.liaisons.views.redirect_for_approval'),
]