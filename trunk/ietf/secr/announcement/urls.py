
from ietf.secr.announcement import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.main),
    url(r'^confirm/$', views.confirm),
]
