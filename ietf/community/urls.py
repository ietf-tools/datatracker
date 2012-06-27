from django.conf.urls.defaults import patterns, url


urlpatterns = patterns('ietf.community.views',
    url(r'^personal/$', 'manage_personal_list', name='manage_personal_list'),
    url(r'^personal/csv/$', 'csv_personal_list', name='csv_personal_list'),
    url(r'^personal/(?P<secret>[a-f0-9]+)/view/$', 'view_personal_list', name='view_personal_list'),
    url(r'^personal/(?P<secret>[a-f0-9]+)/changes/feed/$', 'changes_personal_list', name='changes_personal_list'),
    url(r'^personal/(?P<secret>[a-f0-9]+)/changes/significant/feed/$', 'significant_personal_list', name='significant_personal_list'),
    url(r'^personal/(?P<secret>[a-f0-9]+)/subscribe/$', 'subscribe_personal_list', {'significant': False}, name='subscribe_personal_list'),
    url(r'^personal/(?P<secret>[a-f0-9]+)/subscribe/significant/$', 'subscribe_personal_list', {'significant': True}, name='subscribe_significant_personal_list'),
    url(r'^personal/(?P<secret>[a-f0-9]+)/unsubscribe/$', 'unsubscribe_personal_list', {'significant': False}, name='unsubscribe_personal_list'),
    url(r'^personal/(?P<secret>[a-f0-9]+)/unsubscribe/significant/$', 'unsubscribe_personal_list', {'significant': True}, name='unsubscribe_significant_personal_list'),

    url(r'^group/(?P<acronym>[\w.@+-]+)/$', 'manage_group_list', name='manage_group_list'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/view/$', 'view_group_list', name='view_group_list'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/changes/feed/$', 'changes_group_list', name='changes_group_list'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/changes/significant/feed/$', 'significant_group_list', name='significant_group_list'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/csv/$', 'csv_group_list', name='csv_group_list'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/subscribe/$', 'subscribe_group_list', {'significant': False}, name='subscribe_group_list'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/subscribe/significant/$', 'subscribe_group_list', {'significant': True}, name='subscribe_significant_group_list'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/unsubscribe/$', 'unsubscribe_group_list', {'significant': False}, name='unsubscribe_group_list'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/unsubscribe/significant/$', 'unsubscribe_group_list', {'significant': True}, name='unsubscribe_significant_group_list'),

    url(r'^add_document/(?P<document_name>[^/]+)/$', 'add_document', name='community_add_document'),
    url(r'^(?P<list_id>[\d]+)/remove_document/(?P<document_name>[^/]+)/$', 'remove_document', name='community_remove_document'),
    url(r'^(?P<list_id>[\d]+)/remove_rule/(?P<rule_id>[^/]+)/$', 'remove_rule', name='community_remove_rule'),
    url(r'^(?P<list_id>[\d]+)/subscribe/confirm/(?P<email>[\w.@+-]+)/(?P<date>[\d]+)/(?P<confirm_hash>[a-f0-9]+)/$', 'confirm_subscription', name='confirm_subscription'),
    url(r'^(?P<list_id>[\d]+)/subscribe/significant/confirm/(?P<email>[\w.@+-]+)/(?P<date>[\d]+)/(?P<confirm_hash>[a-f0-9]+)/$', 'confirm_significant_subscription', name='confirm_significant_subscription'),
    url(r'^(?P<list_id>[\d]+)/unsubscribe/confirm/(?P<email>[\w.@+-]+)/(?P<date>[\d]+)/(?P<confirm_hash>[a-f0-9]+)/$', 'confirm_unsubscription', name='confirm_unsubscription'),
    url(r'^(?P<list_id>[\d]+)/unsubscribe/significant/confirm/(?P<email>[\w.@+-]+)/(?P<date>[\d]+)/(?P<confirm_hash>[a-f0-9]+)/$', 'confirm_significant_unsubscription', name='confirm_significant_unsubscription'),
)
