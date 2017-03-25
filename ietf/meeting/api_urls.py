# Copyright The IETF Trust 2007, All Rights Reserved

from ietf.meeting import views
from ietf.utils.urls import url


urlpatterns = [
    url(r'^import_recordings/(?P<number>[A-Za-z0-9._+-]+)/?$', views.api_import_recordings),
]
