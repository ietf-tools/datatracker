from django.conf.urls import url

urlpatterns = [
    url(r'^$', 'ietf.secr.rolodex.views.search', name='rolodex'),
    url(r'^add/$', 'ietf.secr.rolodex.views.add', name='rolodex_add'),
    url(r'^add-proceed/$', 'ietf.secr.rolodex.views.add_proceed', name='rolodex_add_proceed'),
    url(r'^(?P<id>\d{1,6})/edit/$', 'ietf.secr.rolodex.views.edit', name='rolodex_edit'),
    #url(r'^(?P<id>\d{1,6})/delete/$', 'ietf.secr.rolodex.views.delete', name='rolodex_delete'),
    url(r'^(?P<id>\d{1,6})/$', 'ietf.secr.rolodex.views.view', name='rolodex_view'),
]
