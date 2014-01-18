from django.conf.urls import *

urlpatterns = patterns('ietf.secr.console.views',
    url(r'^$', 'main', name='console'),
)
