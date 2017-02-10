# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import url
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy

from ietf.ipr import views

urlpatterns = [
    url(r'^$', views.showlist, name='ipr_showlist'),
    url(r'^about/$', views.about),
    url(r'^admin/$', RedirectView.as_view(url=reverse_lazy('ipr_admin',kwargs={'state':'pending'}), permanent=True),name="ipr_admin_main"),
    url(r'^admin/(?P<state>pending|removed|parked)/$', views.admin, name='ipr_admin'),
    url(r'^ajax/search/$', views.ajax_search, name='ipr_ajax_search'),
    url(r'^by-draft/$', views.by_draft_txt),
    url(r'^by-draft-recursive/$', views.by_draft_recursive_txt),
    url(r'^(?P<id>\d+)/$', views.show, name='ipr_show'),
    url(r'^(?P<id>\d+)/addcomment/$', views.add_comment, name='ipr_add_comment'),
    url(r'^(?P<id>\d+)/addemail/$', views.add_email, name='ipr_add_email'),
    url(r'^(?P<id>\d+)/edit/$', views.edit, name='ipr_edit'),
    url(r'^(?P<id>\d+)/email/$', views.email, name='ipr_email'),
    url(r'^(?P<id>\d+)/history/$', views.history, name='ipr_history'),
    url(r'^(?P<id>\d+)/notify/(?P<type>update|posted)/$', views.notify, name='ipr_notify'),
    url(r'^(?P<id>\d+)/post/$', views.post, name='ipr_post'),
    url(r'^(?P<id>\d+)/state/$', views.state, name='ipr_state'),
    url(r'^update/$', RedirectView.as_view(url=reverse_lazy('ipr_showlist'), permanent=True)),
    url(r'^update/(?P<id>\d+)/$', views.update, name='ipr_update'),
    url(r'^new-(?P<type>(specific|generic|third-party))/$', views.new, name='ipr_new'),
    url(r'^search/$', views.search, name="ipr_search"),
]
