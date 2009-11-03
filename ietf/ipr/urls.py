# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.ipr import views, new, search

urlpatterns = patterns('',
     (r'^$', views.showlist),
     (r'^about/$', views.default),
     (r'^by-draft/$', views.list_drafts),
     #(r'^(?P<removed>removed/)?(?P<ipr_id>\d+)/$', views.show),
     (r'^(?P<ipr_id>\d+)/$', views.show),
     (r'^update/$', views.updatelist),
     (r'^update/(?P<ipr_id>\d+)/$', new.update),
     (r'^new-(?P<type>specific)/$', new.new),
     (r'^new-(?P<type>generic)/$', new.new),
     (r'^new-(?P<type>third-party)/$', new.new),
     (r'^search/$', search.search),     
)




