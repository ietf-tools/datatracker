# Copyright The IETF Trust 2008, All Rights Reserved

from django.conf.urls import patterns
from django.conf import settings

import views_stream

urlpatterns = patterns('',
     (r'^$', views_stream.streams),
     (r'^%(acronym)s/$' % settings.URL_REGEXPS, views_stream.stream_documents, None),
     (r'^%(acronym)s/edit/$' % settings.URL_REGEXPS, views_stream.stream_edit),
)
