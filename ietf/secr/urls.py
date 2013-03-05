from django.conf import settings
from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template

urlpatterns = patterns('',
    url(r'^$', direct_to_template, {'template': 'main.html'}, name="home"),
    (r'^announcement/', include('ietf.secr.announcement.urls')),
    (r'^areas/', include('ietf.secr.areas.urls')),
    (r'^console/', include('ietf.secr.console.urls')),
    (r'^drafts/', include('ietf.secr.drafts.urls')),
    (r'^groups/', include('ietf.secr.groups.urls')),
    (r'^ipradmin/', include('ietf.secr.ipradmin.urls')),
    (r'^meetings/', include('ietf.secr.meetings.urls')),
    (r'^proceedings/', include('ietf.secr.proceedings.urls')),
    (r'^roles/', include('ietf.secr.roles.urls')),
    (r'^rolodex/', include('ietf.secr.rolodex.urls')),
    (r'^sreq/', include('ietf.secr.sreq.urls')),
    (r'^telechat/', include('ietf.secr.telechat.urls')),
)
