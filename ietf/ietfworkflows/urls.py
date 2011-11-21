# Copyright The IETF Trust 2008, All Rights Reserved

from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('ietf.ietfworkflows.views',
     url(r'^(?P<name>[^/]+)/history/$', 'stream_history', name='stream_history'),
     url(r'^(?P<name>[^/]+)/edit/adopt/$', 'edit_adopt', name='edit_adopt'),
     url(r'^(?P<name>[^/]+)/edit/state/$', 'edit_state', name='edit_state'),
     url(r'^(?P<name>[^/]+)/edit/stream/$', 'edit_stream', name='edit_stream'),
     url(r'^delegates/(?P<stream_name>[^/]+)/$', 'stream_delegates', name='stream_delegates'),
)
