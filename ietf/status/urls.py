# Copyright The IETF Trust 2024, All Rights Reserved
# -*- coding: utf-8 -*-

from ietf.status import views
from ietf.utils.urls import url

urlpatterns = [
    url(r"^$", views.status_latest_redirect),
    url(r"^latest$", views.status_latest_html),
    url(r"^latest.json$", views.status_latest_json),
    url(r"(?P<slug>.*)", views.status_page)
]
