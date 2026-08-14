# Copyright The IETF Trust 2009-2025, All Rights Reserved
# -*- coding: utf-8 -*-
from ietf.person import views, ajax
from ietf.utils.urls import url

urlpatterns = [
    url(r'^merge/?$', views.merge),
    url(r'^merge/submit/?$', views.merge_submit),
    url(r'^merge/send_request/?$', views.send_merge_request),
    url(r'^search/(?P<model_name>(person|email))/$', views.ajax_select2_search),
    url(r'^(?P<personid>[0-9]+)/email.json$', ajax.person_email_json),
    url(r'^(?P<email_or_name>[^/]+)$', views.profile),
    url(r'^(?P<email_or_name>[^/]+)/photo/?$', views.photo),
]
