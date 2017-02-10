from django.conf.urls import url

from ietf.secr.console import views

urlpatterns = [
    url(r'^$', views.main, name='console'),
]
