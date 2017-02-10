from django.conf.urls import url

from ietf.sync import views

urlpatterns = [
    url(r'^discrepancies/$', views.discrepancies),
    url(r'^(?P<org>\w+)/notify/(?P<notification>\w+)/$', views.notify),
    url(r'^rfceditor/undo/', views.rfceditor_undo)
]

