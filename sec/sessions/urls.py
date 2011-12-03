from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template, redirect_to

urlpatterns = patterns('sec.sessions.views',
    url(r'^$', 'main', name='sessions'),
    url(r'^status/$', 'tool_status', name='sessions_tool_status'),
    #url(r'^(?P<session_id>\d{1,6})/$', 'view', name='sessions_view'),
    url(r'^new/(?P<group_id>\d{1,6})/$', 'new', name='sessions_new'),
    url(r'^new/(?P<group_id>\d{1,6})/no_session/$', 'no_session', name='sessions_no_session'),
    url(r'^new/(?P<group_id>\d{1,6})/confirm/$', 'confirm', name='sessions_confirm'),
    url(r'^(?P<group>[A-Za-z0-9.-]+)/(?P<meeting>[0-9]+)/$', 'view', name='sessions_view'),
    url(r'^(?P<group>[A-Za-z0-9.-]+)/(?P<meeting>[0-9]+)/cancel/$', 'cancel', name='sessions_cancel'),
    url(r'^(?P<group>[A-Za-z0-9.-]+)/(?P<meeting>[0-9]+)/approve/$', 'approve', name='sessions_approve'),
    url(r'^(?P<group>[A-Za-z0-9.-]+)/(?P<meeting>[0-9]+)/edit/$', 'edit', name='sessions_edit'),
)
