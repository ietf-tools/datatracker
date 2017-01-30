# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import url

urlpatterns = [
    url(r'^(?P<script>.*?\.cgi)(/.*)?$', 'ietf.redirects.views.redirect'),
]
