# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import patterns, url
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy

from ietf.ipr import views, new, search

urlpatterns = patterns('',
     url(r'^$', views.showlist, name='ipr_showlist'),
     (r'^about/$', views.about),
     (r'^by-draft/$', views.iprs_for_drafts_txt),
     url(r'^(?P<ipr_id>\d+)/$', views.show, name='ipr_show'),
     (r'^update/$', RedirectView.as_view(url=reverse_lazy('ipr_showlist'))),
     (r'^update/(?P<ipr_id>\d+)/$', new.update),
     (r'^new-(?P<type>specific)/$', new.new),
     (r'^new-(?P<type>generic)/$', new.new),
     (r'^new-(?P<type>third-party)/$', new.new),
     url(r'^search/$', search.search, name="ipr_search"),
)
