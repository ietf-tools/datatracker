
from ietf.secr.console import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.main),
]
