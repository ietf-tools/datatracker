# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns

urlpatterns = patterns('',
     (r'^(?P<script>.*?\.cgi)(/.*)?$', 'ietf.redirects.views.redirect'),
)
