# Copyright The IETF Trust 2007, 2009, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.ietfauth import views

urlpatterns = patterns('',
        (r'^login/$', views.ietf_login),
        (r'^loggedin/$', views.ietf_loggedin),
	(r'^profile/$', views.profile),
#        (r'^login/(?P<user>[a-z0-9.@]+)/(?P<passwd>.+)$', views.url_login),
)
