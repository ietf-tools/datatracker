
from ietf.secr.rolodex import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.search),
    url(r'^add/$', views.add),
    url(r'^add-proceed/$', views.add_proceed),
    url(r'^(?P<id>\d{1,6})/edit/$', views.edit),
    #url(r'^(?P<id>\d{1,6})/delete/$', views.delete),
    url(r'^(?P<id>\d{1,6})/$', views.view),
]
