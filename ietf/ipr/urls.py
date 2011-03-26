# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns, url
from ietf.ipr import views, new, search
from ietf.utils.lazy import reverse_lazy
from django.views.generic.simple import redirect_to

urlpatterns = patterns('',
     url(r'^$', views.showlist, name='ipr_showlist'),
     (r'^about/$', views.default),
     (r'^by-draft/$', views.list_drafts),
     url(r'^(?P<ipr_id>\d+)/$', views.show, name='ipr_show'),
     (r'^update/$', redirect_to, { 'url': reverse_lazy('ipr_showlist') }),
     (r'^update/(?P<ipr_id>\d+)/$', new.update),
     (r'^new-(?P<type>specific)/$', new.new),
     (r'^new-(?P<type>generic)/$', new.new),
     (r'^new-(?P<type>third-party)/$', new.new),
     (r'^search/$', search.search),     
)




