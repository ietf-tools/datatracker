from django.conf.urls import url

from ietf.help import views

urlpatterns = [
    url(r'^state/(?P<doc>[-\w]+)/(?P<type>[-\w]+)/?$', views.state),
    url(r'^state/(?P<doc>[-\w]+)/?$', views.state),
    url(r'^state/?$', views.state_index),
]

