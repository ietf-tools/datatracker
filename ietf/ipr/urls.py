# Copyright The IETF Trust 2007, All Rights Reserved

from django.views.generic import RedirectView
from django.urls import reverse_lazy

from ietf.ipr import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.showlist),
    url(r'^about/$', views.about),
    url(r'^admin/$', RedirectView.as_view(url=reverse_lazy('ietf.ipr.views.admin',kwargs={'state':'pending'}), permanent=True)),
    url(r'^admin/(?P<state>pending|removed|parked)/$', views.admin),
    url(r'^ajax/search/$', views.ajax_search),
    url(r'^by-draft/$', views.by_draft_txt),
    url(r'^by-draft-recursive/$', views.by_draft_recursive_txt),
    url(r'^(?P<id>\d+)/$', views.show),
    url(r'^(?P<id>\d+)/addcomment/$', views.add_comment),
    url(r'^(?P<id>\d+)/addemail/$', views.add_email),
    url(r'^(?P<id>\d+)/edit/$', views.edit),
    url(r'^(?P<id>\d+)/email/$', views.email),
    url(r'^(?P<id>\d+)/history/$', views.history),
    url(r'^(?P<id>\d+)/notify/(?P<type>update|posted)/$', views.notify),
    url(r'^(?P<id>\d+)/post/$', views.post),
    url(r'^(?P<id>\d+)/state/$', views.state),
    url(r'^update/$', RedirectView.as_view(url=reverse_lazy('ietf.ipr.views.showlist'), permanent=True)),
    url(r'^update/(?P<id>\d+)/$', views.update),
    url(r'^new-(?P<_type>(specific|generic|general|third-party))/$', views.new),
    url(r'^search/$', views.search),
]
