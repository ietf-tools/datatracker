# Copyright The IETF Trust 2007, 2009, All Rights Reserved

from django.conf.urls import url
from django.contrib.auth.views import login, logout

from ietf.ietfauth import views

urlpatterns = [
        url(r'^$', views.index),
        url(r'^confirmnewemail/(?P<auth>[^/]+)/$', views.confirm_new_email),
        url(r'^create/$', views.create_account),
        url(r'^create/confirm/(?P<auth>[^/]+)/$', views.confirm_account),
        url(r'^login/$', login),
        url(r'^logout/$', logout),
        url(r'^password/$', views.change_password),
        url(r'^profile/$', views.profile),
        url(r'^reset/$', views.password_reset),
        url(r'^reset/confirm/(?P<auth>[^/]+)/$', views.confirm_password_reset),
        url(r'^review/$', views.review_overview),
        url(r'^testemail/$', views.test_email),
        url(r'whitelist/add/?$', views.add_account_whitelist),
]
