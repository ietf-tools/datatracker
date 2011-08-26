# Copyright The IETF Trust 2007, 2009, All Rights Reserved

from django.conf.urls.defaults import patterns, url
from ietf.ietfauth import views

urlpatterns = patterns('',
        (r'^$', views.index, None, 'account_index'),
        (r'^login/$', views.ietf_login),
        (r'^loggedin/$', views.ietf_loggedin),
	(r'^profile/$', views.profile),
#        (r'^login/(?P<user>[a-z0-9.@]+)/(?P<passwd>.+)$', views.url_login),
)

urlpatterns += patterns('ietf.ietfauth.views',
        url(r'^create/$', 'create_account', name='create_account'),
        url(r'^confirm/(?P<username>[\w.@+-]+)/(?P<date>[\d]+)/(?P<realm>[\w]+)/(?P<registration_hash>[a-f0-9]+)/$', 'confirm_account', name='confirm_account'),
        url(r'^reset/$', 'password_reset_view', name='password_reset'),
        url(r'^reset/confirm/(?P<username>[\w.@+-]+)/(?P<date>[\d]+)/(?P<realm>[\w]+)/(?P<reset_hash>[a-f0-9]+)/$', 'confirm_password_reset', name='confirm_password_reset'),
        url(r'^ajax/check_username/$', 'ajax_check_username', name='ajax_check_username'),

)
