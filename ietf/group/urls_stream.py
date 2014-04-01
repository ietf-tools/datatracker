# Copyright The IETF Trust 2008, All Rights Reserved

from django.conf.urls import patterns

import views_stream

urlpatterns = patterns('',
     (r'^$', views_stream.streams),
     (r'^(?P<acronym>[a-zA-Z0-9-]+)/$', views_stream.stream_documents, None),
     (r'^(?P<acronym>[a-zA-Z0-9-]+)/edit/$', views_stream.stream_edit),
)
