from django.conf.urls import patterns, url

urlpatterns = patterns('ietf.secr.console.views',
    url(r'^$', 'main', name='console'),
)
