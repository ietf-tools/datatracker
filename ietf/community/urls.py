from django.conf.urls import patterns, url


urlpatterns = patterns('',
    url(r'^personal/(?P<username>[^/]+)/$', 'ietf.community.views.view_list', name='community_personal_view_list'),
    url(r'^personal/(?P<username>[^/]+)/manage/$', 'ietf.community.views.manage_list', name='community_personal_manage_list'),
    url(r'^personal/(?P<username>[^/]+)/trackdocument/(?P<name>[^/]+)/$', 'ietf.community.views.track_document', name='community_personal_track_document'),
    url(r'^personal/(?P<username>[^/]+)/untrackdocument/(?P<name>[^/]+)/$', 'ietf.community.views.untrack_document', name='community_personal_untrack_document'),
    url(r'^personal/(?P<username>[^/]+)/csv/$', 'ietf.community.views.export_to_csv', name='community_personal_csv'),
    url(r'^personal/(?P<username>[^/]+)/feed/$', 'ietf.community.views.feed', name='community_personal_feed'),
    url(r'^personal/(?P<username>[^/]+)/subscription/$', 'ietf.community.views.subscription', name='community_personal_subscription'),

)
