# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns, url
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy

urlpatterns = patterns('ietf.ipr.views',
     url(r'^$', 'showlist', name='ipr_showlist'),
     (r'^about/$', 'about'),
     url(r'^admin/$', RedirectView.as_view(url=reverse_lazy('ipr_admin',kwargs={'state':'pending'}), permanent=True),name="ipr_admin_main"),
     url(r'^admin/(?P<state>pending|removed|parked)/$', 'admin', name='ipr_admin'),
     url(r'^ajax/search/$', 'ajax_search', name='ipr_ajax_search'),
     url(r'^by-draft/$', 'by_draft_txt'),
     url(r'^by-draft-recursive/$', 'by_draft_recursive_txt'),
     url(r'^(?P<id>\d+)/$', 'show', name='ipr_show'),
     url(r'^(?P<id>\d+)/addcomment/$', 'add_comment', name='ipr_add_comment'),
     url(r'^(?P<id>\d+)/addemail/$', 'add_email', name='ipr_add_email'),
     url(r'^(?P<id>\d+)/edit/$', 'edit', name='ipr_edit'),
     url(r'^(?P<id>\d+)/email/$', 'email', name='ipr_email'),
     url(r'^(?P<id>\d+)/history/$', 'history', name='ipr_history'),
     url(r'^(?P<id>\d+)/notify/(?P<type>update|posted)/$', 'notify', name='ipr_notify'),
     url(r'^(?P<id>\d+)/post/$', 'post', name='ipr_post'),
     url(r'^(?P<id>\d+)/state/$', 'state', name='ipr_state'),
     (r'^update/$', RedirectView.as_view(url=reverse_lazy('ipr_showlist'), permanent=True)),
     url(r'^update/(?P<id>\d+)/$', 'update', name='ipr_update'),
     url(r'^new-(?P<type>(specific|generic|third-party))/$', 'new', name='ipr_new'),
     url(r'^search/$', 'search', name="ipr_search"),
)
