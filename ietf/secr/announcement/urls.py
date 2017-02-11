
from ietf.secr.announcement import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.main, name='announcement'),
    url(r'^confirm/$', views.confirm, name='announcement_confirm'),
]
