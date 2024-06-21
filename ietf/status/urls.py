# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.conf import settings

from ietf.status import views
from ietf.utils.urls import url

urlpatterns = [
    url(r"^$", views.status_index),
    url(r"^index.json$", views.status_index_json),
]
