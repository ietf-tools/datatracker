from django.conf.urls import patterns, url

urlpatterns = patterns('ietf.secr.announcement.views',
    url(r'^$', 'main', name='announcement'),
    url(r'^confirm/$', 'confirm', name='announcement_confirm'),
)
