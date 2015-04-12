# Copyright The IETF Trust 2007, 2009, All Rights Reserved

from django.conf.urls import patterns, url
from django.contrib.auth.views import login, logout

urlpatterns = patterns('ietf.ietfauth.views',
        url(r'^$', 'index', name='account_index'),
#        url(r'^login/$', 'ietf_login'),
        url(r'^login/$', login),
        url(r'^logout/$', logout),
#        url(r'^loggedin/$', 'ietf_loggedin'),
#        url(r'^loggedout/$', 'logged_out'),
        url(r'^profile/$', 'profile'),
#        (r'^login/(?P<user>[a-z0-9.@]+)/(?P<passwd>.+)$', 'url_login'),
        url(r'^testemail/$', 'test_email'),
        url(r'^create/$', 'create_account', name='create_account'),
        url(r'^confirm/(?P<username>[\w.@+-]+)/(?P<date>[\d]+)/(?P<realm>[\w]+)/(?P<hash>[a-f0-9]+)/$', 'confirm_account', name='confirm_account'),
        url(r'^reset/$', 'password_reset_view', name='password_reset'),
        url(r'^reset/confirm/(?P<username>[\w.@+-]+)/(?P<date>[\d]+)/(?P<realm>[\w]+)/(?P<hash>[a-f0-9]+)/$', 'confirm_password_reset', name='confirm_password_reset'),
        url(r'^add_email/confirm/(?P<username>[\w.@+-]+)/(?P<date>[\d]+)/(?P<email>[\w.@+-]+)/(?P<hash>[a-f0-9]+)/$', 'confirm_new_email', name='confirm_new_email'),
#        url(r'^ajax/check_username/$', 'ajax_check_username', name='ajax_check_username'),
)
