from django.conf.urls.defaults import *

urlpatterns = patterns('ietf.secr.announcement.views',
    url(r'^$', 'main', name='announcement'),
    url(r'^confirm/$', 'confirm', name='announcement_confirm'),
)
