from django.conf.urls import patterns, url


urlpatterns = patterns('ietf.community.views',
    url(r'^personal/(?P<username>[^/]+)/$', 'view_list', name='community_personal_view_list'),
    url(r'^personal/(?P<username>[^/]+)/manage/$', 'manage_list', name='community_personal_manage_list'),
    url(r'^personal/(?P<username>[^/]+)/trackdocument/(?P<name>[^/]+)/$', 'track_document', name='community_personal_track_document'),
    url(r'^personal/(?P<username>[^/]+)/untrackdocument/(?P<name>[^/]+)/$', 'untrack_document', name='community_personal_untrack_document'),
    url(r'^personal/(?P<username>[^/]+)/csv/$', 'export_to_csv', name='community_personal_csv'),
    url(r'^personal/(?P<username>[^/]+)/feed/$', 'feed', name='community_personal_feed'),
    url(r'^personal/(?P<username>[^/]+)/subscription/$', 'subscription', name='community_personal_subscription'),

    url(r'^group/(?P<acronym>[\w.@+-]+)/$', 'view_list', name='community_group_view_list'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/manage/$', 'manage_list', name='community_group_manage_list'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/trackdocument/(?P<name>[^/]+)/$', 'track_document', name='community_group_track_document'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/untrackdocument/(?P<name>[^/]+)/$', 'untrack_document', name='community_group_untrack_document'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/csv/$', 'export_to_csv', name='community_group_csv'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/feed/$', 'feed', name='community_group_feed'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/subscription/$', 'subscription', name='community_group_subscription'),
)
