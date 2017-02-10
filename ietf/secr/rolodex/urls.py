from django.conf.urls import url

from ietf.secr.rolodex import views

urlpatterns = [
    url(r'^$', views.search, name='rolodex'),
    url(r'^add/$', views.add, name='rolodex_add'),
    url(r'^add-proceed/$', views.add_proceed, name='rolodex_add_proceed'),
    url(r'^(?P<id>\d{1,6})/edit/$', views.edit, name='rolodex_edit'),
    #url(r'^(?P<id>\d{1,6})/delete/$', views.delete, name='rolodex_delete'),
    url(r'^(?P<id>\d{1,6})/$', views.view, name='rolodex_view'),
]
