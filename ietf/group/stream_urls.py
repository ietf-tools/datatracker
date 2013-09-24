# Copyright The IETF Trust 2008, All Rights Reserved

from django.conf.urls.defaults import patterns, include

import views

urlpatterns = patterns('',
     (r'^$', views.streams),
     (r'^(?P<acronym>[a-zA-Z0-9-]+)/$', views.stream_documents, None),
     (r'^(?P<acronym>[a-zA-Z0-9-]+)/edit/$', views.stream_edit),
#     (r'^(?P<acronym>[a-zA-Z0-9-]+)/history/$', views.stream_history),
#     (r'^(?P<acronym>[a-zA-Z0-9-]+)/edit/$', views.stream_edit)
     (r'^management/', include('ietf.ietfworkflows.urls')),

)
