# Copyright The IETF Trust 2008, All Rights Reserved

from django.conf.urls import url
from django.conf import settings

import views_stream

urlpatterns = [
    url(r'^$', views_stream.streams),
    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, views_stream.stream_documents, None),
    url(r'^%(acronym)s/edit/$' % settings.URL_REGEXPS, views_stream.stream_edit),
]
