from django.conf.urls.defaults import *

urlpatterns = patterns('ietf.secr.console.views',
    url(r'^$', 'main', name='console'),
)
