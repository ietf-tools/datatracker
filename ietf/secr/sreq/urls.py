from django.conf.urls import url
from django.conf import settings

urlpatterns = [
    url(r'^$', 'ietf.secr.sreq.views.main', name='sessions'),
    url(r'^status/$', 'ietf.secr.sreq.views.tool_status', name='sessions_tool_status'),
    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, 'ietf.secr.sreq.views.view', name='sessions_view'),
    url(r'^(?P<num>[A-Za-z0-9_\-\+]+)/%(acronym)s/view/$' % settings.URL_REGEXPS, 'ietf.secr.sreq.views.view', name='sessions_view'),
    url(r'^%(acronym)s/approve/$' % settings.URL_REGEXPS, 'ietf.secr.sreq.views.approve', name='sessions_approve'),
    url(r'^%(acronym)s/cancel/$' % settings.URL_REGEXPS, 'ietf.secr.sreq.views.cancel', name='sessions_cancel'),
    url(r'^%(acronym)s/confirm/$' % settings.URL_REGEXPS, 'ietf.secr.sreq.views.confirm', name='sessions_confirm'),
    url(r'^%(acronym)s/edit/$' % settings.URL_REGEXPS, 'ietf.secr.sreq.views.edit', name='sessions_edit'),
    url(r'^%(acronym)s/new/$' % settings.URL_REGEXPS, 'ietf.secr.sreq.views.new', name='sessions_new'),
    url(r'^%(acronym)s/no_session/$' % settings.URL_REGEXPS, 'ietf.secr.sreq.views.no_session', name='sessions_no_session'),
    url(r'^(?P<num>[A-Za-z0-9_\-\+]+)/%(acronym)s/edit/$' % settings.URL_REGEXPS, 'ietf.secr.sreq.views.edit_mtg', name='sessions_edit'),
]
