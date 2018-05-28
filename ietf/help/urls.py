# Copyright The IETF Trust 2013-2018, All Rights Reserved

from django.views.generic import TemplateView

from ietf.help import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^state/(?P<doc>[-\w]+)/(?P<type>[-\w]+)/?$', views.state),
    url(r'^state/(?P<doc>[-\w]+)/?$', views.state),
    url(r'^state/?$', views.state_index),
    url(r'^personal-information/?$', TemplateView.as_view(template_name='help/personal-information.html'), name='personal-information'),
]

