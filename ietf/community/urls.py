

from ietf.community import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^personal/(?P<email_or_name>[^/]+)/$', views.view_list),
    url(r'^personal/(?P<email_or_name>[^/]+)/manage/$', views.manage_list),
    url(r'^personal/(?P<email_or_name>[^/]+)/trackdocument/(?P<name>[^/]+)/$', views.track_document),
    url(r'^personal/(?P<email_or_name>[^/]+)/untrackdocument/(?P<name>[^/]+)/$', views.untrack_document),
    url(r'^personal/(?P<email_or_name>[^/]+)/csv/$', views.export_to_csv),
    url(r'^personal/(?P<email_or_name>[^/]+)/feed/$', views.feed),
    url(r'^personal/(?P<email_or_name>[^/]+)/subscription/$', views.subscription),
]
