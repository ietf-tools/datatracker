# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.urls import path
from ietf.status import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.status_index),
    url(r'^latest.html$', views.status_latest_html),
    url(r'^latest.json$', views.status_latest_json),
    # url(r'^(?P<slug>\w+)$', views.status_page),
    path("<slug:slug>/", views.status_page) 
]
