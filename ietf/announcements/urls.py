# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns

from django.conf import settings

urlpatterns = patterns('',
    (r'^nomcom/$', 'ietf.announcements.views.nomcom'),
    (r'^nomcom/(?P<object_id>\d+)/$', 'ietf.announcements.views.message_detail'))
)
