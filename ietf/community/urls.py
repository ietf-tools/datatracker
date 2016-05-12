from django.conf.urls import patterns, url


urlpatterns = patterns('',
    url(r'^personal/(?P<username>[^/]+)/$', 'ietf.community.views.view_list'),
    url(r'^personal/(?P<username>[^/]+)/manage/$', 'ietf.community.views.manage_list'),
    url(r'^personal/(?P<username>[^/]+)/trackdocument/(?P<name>[^/]+)/$', 'ietf.community.views.track_document'),
    url(r'^personal/(?P<username>[^/]+)/untrackdocument/(?P<name>[^/]+)/$', 'ietf.community.views.untrack_document'),
    url(r'^personal/(?P<username>[^/]+)/csv/$', 'ietf.community.views.export_to_csv'),
    url(r'^personal/(?P<username>[^/]+)/feed/$', 'ietf.community.views.feed'),
    url(r'^personal/(?P<username>[^/]+)/subscription/$', 'ietf.community.views.subscription'),

)
