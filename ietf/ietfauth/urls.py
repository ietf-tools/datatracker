# Copyright The IETF Trust 2007, 2009, All Rights Reserved

from django.conf.urls import patterns, url
from django.contrib.auth.views import login, logout

urlpatterns = patterns('ietf.ietfauth.views',
        url(r'^$', 'index', name='account_index'),
#        url(r'^login/$', 'ietf_login'),
        url(r'^login/$', login, name="account_login"),
        url(r'^logout/$', logout, name="account_logout"),
#        url(r'^loggedin/$', 'ietf_loggedin'),
#        url(r'^loggedout/$', 'logged_out'),
        url(r'^profile/$', 'profile', name="account_profile"),
#        (r'^login/(?P<user>[a-z0-9.@]+)/(?P<passwd>.+)$', 'url_login'),
        url(r'^testemail/$', 'test_email'),
        url(r'^create/$', 'create_account', name='create_account'),
        url(r'^create/confirm/(?P<auth>[^/]+)/$', 'confirm_account', name='confirm_account'),
        url(r'^reset/$', 'password_reset', name='password_reset'),
        url(r'^reset/confirm/(?P<auth>[^/]+)/$', 'confirm_password_reset', name='confirm_password_reset'),
        url(r'^confirmnewemail/(?P<auth>[^/]+)/$', 'confirm_new_email', name='confirm_new_email'),
)
