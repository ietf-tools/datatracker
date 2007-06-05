from django.conf.urls.defaults import patterns

urlpatterns = patterns('',
     (r'^(?P<script>.*.cgi)$', 'ietf.redirects.views.redirect'),
)
