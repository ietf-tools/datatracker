from django.conf.urls.defaults import *

urlpatterns = patterns('ietf.secr.rolodex.views',
    url(r'^$', 'search', name='rolodex'),
    url(r'^add/$', 'add', name='rolodex_add'),
    url(r'^add-proceed/$', 'add_proceed', name='rolodex_add_proceed'),
    url(r'^(?P<id>\d{1,6})/edit/$', 'edit', name='rolodex_edit'),
    #url(r'^(?P<id>\d{1,6})/delete/$', 'delete', name='rolodex_delete'),
    url(r'^(?P<id>\d{1,6})/$', 'view', name='rolodex_view'),
)
