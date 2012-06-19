from django.conf.urls.defaults import *

urlpatterns = patterns('sec.console.views',
    url(r'^$', 'main', name='console'),
)
