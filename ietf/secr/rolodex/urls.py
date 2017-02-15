
from ietf.secr.rolodex import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.search, name='rolodex'),
    url(r'^add/$', views.add, name='rolodex_add'),
    url(r'^add-proceed/$', views.add_proceed),
    url(r'^(?P<id>\d{1,6})/edit/$', views.edit),
    #url(r'^(?P<id>\d{1,6})/delete/$', views.delete, name='rolodex_delete'),
    url(r'^(?P<id>\d{1,6})/$', views.view, name='rolodex_view'),
]
