# Copyright The IETF Trust 2007, 2009, All Rights Reserved

from django.conf.urls import patterns, url
from django.contrib.auth.views import login, logout

from ietf.ietfauth.views import add_account_whitelist

urlpatterns = patterns('ietf.ietfauth.views',
        url(r'^$', 'index'),
#        url(r'^login/$', 'ietf_login'),
        url(r'^login/$', login),
        url(r'^logout/$', logout),
#        url(r'^loggedin/$', 'ietf_loggedin'),
#        url(r'^loggedout/$', 'logged_out'),
        url(r'^profile/$', 'profile'),
#        (r'^login/(?P<user>[a-z0-9.@]+)/(?P<passwd>.+)$', 'url_login'),
        url(r'^testemail/$', 'test_email'),
        url(r'^create/$', 'create_account'),
        url(r'^create/confirm/(?P<auth>[^/]+)/$', 'confirm_account'),
        url(r'^reset/$', 'password_reset'),
        url(r'^reset/confirm/(?P<auth>[^/]+)/$', 'confirm_password_reset'),
        url(r'^confirmnewemail/(?P<auth>[^/]+)/$', 'confirm_new_email'),
        (r'whitelist/add/?$', add_account_whitelist),
)
