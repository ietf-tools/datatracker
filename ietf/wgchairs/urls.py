# Copyright The IETF Trust 2008, All Rights Reserved

from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('ietf.wgchairs.views',
     url(r'^delegates/$', 'manage_delegates', name='manage_delegates'),
)
