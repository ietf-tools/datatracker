from django.conf.urls import url

from ietf.secr.announcement import views

urlpatterns = [
    url(r'^$', views.main, name='announcement'),
    url(r'^confirm/$', views.confirm, name='announcement_confirm'),
]
