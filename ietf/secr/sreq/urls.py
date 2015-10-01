from django.conf.urls import patterns, url
from django.conf import settings

urlpatterns = patterns('ietf.secr.sreq.views',
    url(r'^$', 'main', name='sessions'),
    url(r'^status/$', 'tool_status', name='sessions_tool_status'),
    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, 'view', name='sessions_view'),
    url(r'^(?P<num>[A-Za-z0-9_\-\+]+)/%(acronym)s/view/$' % settings.URL_REGEXPS, 'view', name='sessions_view'),
    url(r'^%(acronym)s/approve/$' % settings.URL_REGEXPS, 'approve', name='sessions_approve'),
    url(r'^%(acronym)s/cancel/$' % settings.URL_REGEXPS, 'cancel', name='sessions_cancel'),
    url(r'^%(acronym)s/confirm/$' % settings.URL_REGEXPS, 'confirm', name='sessions_confirm'),
    url(r'^%(acronym)s/edit/$' % settings.URL_REGEXPS, 'edit', name='sessions_edit'),
    url(r'^%(acronym)s/new/$' % settings.URL_REGEXPS, 'new', name='sessions_new'),
    url(r'^%(acronym)s/no_session/$' % settings.URL_REGEXPS, 'no_session', name='sessions_no_session'),
    url(r'^(?P<num>[A-Za-z0-9_\-\+]+)/%(acronym)s/edit/$' % settings.URL_REGEXPS, 'edit_mtg', name='sessions_edit'),
)
