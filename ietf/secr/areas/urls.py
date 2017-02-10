from django.conf.urls import url

from ietf.secr.areas import views

urlpatterns = [
    url(r'^$', views.list_areas, name='areas'),
    url(r'^add/$', views.add, name='areas_add'),
    url(r'^getemails', views.getemails, name='areas_emails'),
    url(r'^getpeople', views.getpeople, name='areas_getpeople'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/$', views.view, name='areas_view'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/edit/$', views.edit, name='areas_edit'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/people/$', views.people, name='areas_people'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/people/modify/$', views.modify, name='areas_modify'),
]
