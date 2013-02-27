from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    url(r'^state/(?P<doc>[-\w]+)/(?P<type>[-\w]+)/?$', 'ietf.help.views.state'),
    url(r'^state/(?P<doc>[-\w]+)/?$', 'ietf.help.views.state'),
)

