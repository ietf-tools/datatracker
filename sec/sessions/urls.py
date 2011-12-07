from django.conf.urls.defaults import *

urlpatterns = patterns('sec.sessions.views',
    url(r'^$', 'main', name='sessions'),
    url(r'^status/$', 'tool_status', name='sessions_tool_status'),
    url(r'^(?P<group_id>\d{1,6})/$', 'view', name='sessions_view'),
    url(r'^(?P<group_id>\d{1,6})/approve/$', 'approve', name='sessions_approve'),
    url(r'^(?P<group_id>\d{1,6})/cancel/$', 'cancel', name='sessions_cancel'),
    url(r'^(?P<group_id>\d{1,6})/confirm/$', 'confirm', name='sessions_confirm'),
    url(r'^(?P<group_id>\d{1,6})/edit/$', 'edit', name='sessions_edit'),
    url(r'^(?P<group_id>\d{1,6})/new/$', 'new', name='sessions_new'),
    url(r'^(?P<group_id>\d{1,6})/no_session/$', 'no_session', name='sessions_no_session'),
)
