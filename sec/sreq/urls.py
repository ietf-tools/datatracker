from django.conf.urls.defaults import *

urlpatterns = patterns('sec.sreq.views',
    url(r'^$', 'main', name='sessions'),
    url(r'^status/$', 'tool_status', name='sessions_tool_status'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+]+)/$', 'view', name='sessions_view'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+]+)/approve/$', 'approve', name='sessions_approve'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+]+)/cancel/$', 'cancel', name='sessions_cancel'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+]+)/confirm/$', 'confirm', name='sessions_confirm'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+]+)/edit/$', 'edit', name='sessions_edit'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+]+)/new/$', 'new', name='sessions_new'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+]+)/no_session/$', 'no_session', name='sessions_no_session'),
)
