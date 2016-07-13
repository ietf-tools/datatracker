from django.conf.urls import patterns, url

urlpatterns = patterns('ietf.secr.sreq.views',
    url(r'^$', 'main', name='sessions'),
    url(r'^status/$', 'tool_status', name='sessions_tool_status'),
    url(r'^(?P<acronym>[-a-z0-9]+)/$', 'view', name='sessions_view'),
    url(r'^(?P<num>[A-Za-z0-9_\-\+]+)/(?P<acronym>[-a-z0-9]+)/view/$', 'view', name='sessions_view'),
    url(r'^(?P<acronym>[-a-z0-9]+)/approve/$', 'approve', name='sessions_approve'),
    url(r'^(?P<acronym>[-a-z0-9]+)/cancel/$', 'cancel', name='sessions_cancel'),
    url(r'^(?P<acronym>[-a-z0-9]+)/confirm/$', 'confirm', name='sessions_confirm'),
    url(r'^(?P<acronym>[-a-z0-9]+)/edit/$', 'edit', name='sessions_edit'),
    url(r'^(?P<acronym>[-a-z0-9]+)/new/$', 'new', name='sessions_new'),
    url(r'^(?P<acronym>[-a-z0-9]+)/no_session/$', 'no_session', name='sessions_no_session'),
    url(r'^(?P<num>[A-Za-z0-9_\-\+]+)/(?P<acronym>[-a-z0-9]+)/edit/$', 'edit_mtg', name='sessions_edit'),
)
