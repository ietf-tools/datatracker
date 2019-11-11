# Copyright The IETF Trust 2007-2019, All Rights Reserved

from django.views.generic import RedirectView, TemplateView

from ietf.liaisons import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^help/$', TemplateView.as_view(template_name='liaisons/help.html')),
    url(r'^help/fields/$', TemplateView.as_view(template_name='liaisons/field_help.html'), name='liaison-help-fields'),
    url(r'^help/from_ietf/$', TemplateView.as_view(template_name='liaisons/guide_from_ietf.html')),
    url(r'^help/to_ietf/$', TemplateView.as_view(template_name='liaisons/guide_to_ietf.html')),
    url(r'^managers/$', RedirectView.as_view(url='https://www.ietf.org/liaison/managers.html', permanent=True)),
]

# AJAX views
urlpatterns += [ 
    url(r'^ajax/get_info/$', views.ajax_get_liaison_info),
    url(r'^ajax/select2search/$', views.ajax_select2_search_liaison_statements),
]

# Views
urlpatterns += [ 
    url(r'^$', views.liaison_list),
    url(r'^(?P<state>(posted|pending|dead))/', views.liaison_list),
    url(r'^(?P<object_id>\d+)/$', views.liaison_detail),
    url(r'^(?P<object_id>\d+)/addcomment/$', views.add_comment),
    url(r'^(?P<object_id>\d+)/edit/$', views.liaison_edit),
    url(r'^(?P<object_id>\d+)/edit-attachment/(?P<doc_id>[A-Za-z0-9._+-]+)$', views.liaison_edit_attachment),
    url(r'^(?P<object_id>\d+)/delete-attachment/(?P<attach_id>[A-Za-z0-9._+-]+)$', views.liaison_delete_attachment),
    url(r'^(?P<object_id>\d+)/history/$', views.liaison_history),
    url(r'^(?P<object_id>\d+)/reply/$', views.liaison_reply),
    url(r'^(?P<object_id>\d+)/resend/$', views.liaison_resend),
    url(r'^add/(?P<type>(incoming|outgoing))/$', views.liaison_add),

    # Redirects for backwards compatibility
    url(r'^add/$', views.redirect_add),
    url(r'^for_approval/$', views.redirect_for_approval),
    url(r'^for_approval/(?P<object_id>\d+)/$', views.redirect_for_approval),
]
