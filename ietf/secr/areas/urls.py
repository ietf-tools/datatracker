
from ietf.secr.areas import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.list_areas),
    url(r'^add/$', views.add),
    url(r'^getemails', views.getemails),
    url(r'^getpeople', views.getpeople),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/$', views.view),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/edit/$', views.edit),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/people/$', views.people),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/people/modify/$', views.modify),
]
