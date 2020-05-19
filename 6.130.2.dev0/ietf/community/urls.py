

from ietf.community import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^personal/(?P<username>[^/]+)/$', views.view_list),
    url(r'^personal/(?P<username>[^/]+)/manage/$', views.manage_list),
    url(r'^personal/(?P<username>[^/]+)/trackdocument/(?P<name>[^/]+)/$', views.track_document),
    url(r'^personal/(?P<username>[^/]+)/untrackdocument/(?P<name>[^/]+)/$', views.untrack_document),
    url(r'^personal/(?P<username>[^/]+)/csv/$', views.export_to_csv),
    url(r'^personal/(?P<username>[^/]+)/feed/$', views.feed),
    url(r'^personal/(?P<username>[^/]+)/subscription/$', views.subscription),
]
