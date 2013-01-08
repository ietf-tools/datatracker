from django.conf import settings
from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template

urlpatterns = patterns('',
    url(r'^$', direct_to_template, {'template': 'main.html'}, name="home"),
    (r'^sreq/', include('ietf.secr.sreq.urls')),
)
