from django.conf.urls.defaults import *

urlpatterns = patterns('',
     (r'^(?P<script>.*.cgi)$', 'ietf.redirects.views.redirect'),
)
