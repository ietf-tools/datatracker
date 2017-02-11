# Copyright The IETF Trust 2007, All Rights Reserved


from ietf.redirects import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^(?P<script>.*?\.cgi)(/.*)?$', views.redirect),
]
