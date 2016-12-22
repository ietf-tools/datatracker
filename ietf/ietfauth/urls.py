# Copyright The IETF Trust 2007, 2009, All Rights Reserved

from django.conf.urls import url
from django.contrib.auth.views import login, logout

from ietf.ietfauth.views import add_account_whitelist

urlpatterns = [
        url(r'^$', 'ietf.ietfauth.views.index'),
#        url(r'^login/$', 'ietf.ietfauth.views.ietf_login'),
        url(r'^login/$', login),
        url(r'^logout/$', logout),
#        url(r'^loggedin/$', 'ietf.ietfauth.views.ietf_loggedin'),
#        url(r'^loggedout/$', 'ietf.ietfauth.views.logged_out'),
        url(r'^profile/$', 'ietf.ietfauth.views.profile'),
#        (r'^login/(?P<user>[a-z0-9.@]+)/(?P<passwd>.+)$', 'ietf.ietfauth.views.url_login'),
        url(r'^testemail/$', 'ietf.ietfauth.views.test_email'),
        url(r'^create/$', 'ietf.ietfauth.views.create_account'),
        url(r'^create/confirm/(?P<auth>[^/]+)/$', 'ietf.ietfauth.views.confirm_account'),
        url(r'^reset/$', 'ietf.ietfauth.views.password_reset'),
        url(r'^reset/confirm/(?P<auth>[^/]+)/$', 'ietf.ietfauth.views.confirm_password_reset'),
        url(r'^confirmnewemail/(?P<auth>[^/]+)/$', 'ietf.ietfauth.views.confirm_new_email'),
        url(r'whitelist/add/?$', add_account_whitelist),
        url(r'^review/$', 'ietf.ietfauth.views.review_overview'),
]
