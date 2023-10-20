# Copyright The IETF Trust 2023, All Rights Reserved

from ietf.api import views_dashboard

from ietf.utils.urls import url

urlpatterns = [
    url(r'^groups_opened_closed/$', views_dashboard.groups_opened_closed),
    url(r'^submissions/$', views_dashboard.submissions),
    url(r'^interims/$', views_dashboard.interims),
    url(r'^registration/$', views_dashboard.registration),
]


