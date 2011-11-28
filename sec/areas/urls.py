from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template, redirect_to
from django.views.generic import list_detail

urlpatterns = patterns('sec.areas.views',
    url(r'^$', 'list_areas', name='areas'),
    url(r'^add/$', 'add', name='areas_add'),
    url(r'^getemails', 'getemails', name='areas_emails'),
    url(r'^getpeople', 'getpeople', name='areas_getpeople'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/$', 'view', name='areas_view'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/edit/$', 'edit', name='areas_edit'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/people/$', 'people', name='areas_people'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/people/modify/$', 'modify', name='areas_modify'),
)
