# Copyright The IETF Trust 2007-2019, All Rights Reserved
# Copyright The IETF Trust 2007, 2009, All Rights Reserved

from django.contrib.auth.views import logout # type: ignore

from ietf.ietfauth import views
from ietf.utils.urls import url

urlpatterns = [
        url(r'^$', views.index),
        url(r'^apikey/?$', views.apikey_index),
        url(r'^apikey/add/?$', views.apikey_create),
        url(r'^apikey/del/?$', views.apikey_disable),
        url(r'^confirmnewemail/(?P<auth>[^/]+)/$', views.confirm_new_email),
        url(r'^create/$', views.create_account),
        url(r'^create/confirm/(?P<auth>[^/]+)/$', views.confirm_account),
        url(r'^login/$', views.login),
        url(r'^logout/$', logout),
        url(r'^password/$', views.change_password),
        url(r'^profile/$', views.profile),
        url(r'^reset/$', views.password_reset),
        url(r'^reset/confirm/(?P<auth>[^/]+)/$', views.confirm_password_reset),
        url(r'^review/$', views.review_overview),
        url(r'^testemail/$', views.test_email),
        url(r'^username/$', views.change_username),
        url(r'^whitelist/add/?$', views.add_account_whitelist),
]
