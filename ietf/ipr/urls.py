# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import url
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy

urlpatterns = [
    url(r'^$', 'ietf.ipr.views.showlist', name='ipr_showlist'),
    url(r'^about/$', 'ietf.ipr.views.about'),
    url(r'^admin/$', RedirectView.as_view(url=reverse_lazy('ipr_admin',kwargs={'state':'pending'}), permanent=True),name="ipr_admin_main"),
    url(r'^admin/(?P<state>pending|removed|parked)/$', 'ietf.ipr.views.admin', name='ipr_admin'),
    url(r'^ajax/search/$', 'ietf.ipr.views.ajax_search', name='ipr_ajax_search'),
    url(r'^by-draft/$', 'ietf.ipr.views.by_draft_txt'),
    url(r'^by-draft-recursive/$', 'ietf.ipr.views.by_draft_recursive_txt'),
    url(r'^(?P<id>\d+)/$', 'ietf.ipr.views.show', name='ipr_show'),
    url(r'^(?P<id>\d+)/addcomment/$', 'ietf.ipr.views.add_comment', name='ipr_add_comment'),
    url(r'^(?P<id>\d+)/addemail/$', 'ietf.ipr.views.add_email', name='ipr_add_email'),
    url(r'^(?P<id>\d+)/edit/$', 'ietf.ipr.views.edit', name='ipr_edit'),
    url(r'^(?P<id>\d+)/email/$', 'ietf.ipr.views.email', name='ipr_email'),
    url(r'^(?P<id>\d+)/history/$', 'ietf.ipr.views.history', name='ipr_history'),
    url(r'^(?P<id>\d+)/notify/(?P<type>update|posted)/$', 'ietf.ipr.views.notify', name='ipr_notify'),
    url(r'^(?P<id>\d+)/post/$', 'ietf.ipr.views.post', name='ipr_post'),
    url(r'^(?P<id>\d+)/state/$', 'ietf.ipr.views.state', name='ipr_state'),
    url(r'^update/$', RedirectView.as_view(url=reverse_lazy('ipr_showlist'), permanent=True)),
    url(r'^update/(?P<id>\d+)/$', 'ietf.ipr.views.update', name='ipr_update'),
    url(r'^new-(?P<type>(specific|generic|third-party))/$', 'ietf.ipr.views.new', name='ipr_new'),
    url(r'^search/$', 'ietf.ipr.views.search', name="ipr_search"),
]
