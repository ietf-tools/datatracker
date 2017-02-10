# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import url

from ietf.redirects import views

urlpatterns = [
    url(r'^(?P<script>.*?\.cgi)(/.*)?$', views.redirect),
]
