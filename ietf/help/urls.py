# Copyright The IETF Trust 2013-2022, All Rights Reserved

from ietf.help import views
from ietf.utils.urls import url
from django.views.generic import RedirectView

urlpatterns = [
    url(r'^state/(?P<doc>[-\w]+)/(?P<type>[-\w]+)/?$', views.state),
    url(r'^state/(?P<doc>[-\w]+)/?$', views.state),
    url(r'^state/?$', RedirectView.as_view(url='/doc/help/state/', permanent=True)),
]
