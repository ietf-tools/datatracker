# Copyright The IETF Trust 2007, 2009, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.ietfauth import views

urlpatterns = patterns('django.contrib.auth.views',
	(r'^login/$', 'login'),
	(r'^logout/$', 'logout'),
)
urlpatterns += patterns('',
        (r'^$', 'django.views.generic.simple.direct_to_template', {'template': 'registration/account_info.html'}),
	(r'^profile/$', views.my)
)
