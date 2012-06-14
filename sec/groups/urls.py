from django.conf.urls.defaults import *
from django.contrib import admin

import sec.groups

urlpatterns = patterns('sec.groups.views',
    url(r'^$', 'search', name='groups'),
    url(r'^add/$', 'add', name='groups_add'),
    url(r'^blue-dot-report/$', 'blue_dot', name='groups_blue_dot'),
    url(r'^search/$', 'search', name='groups_search'),
    #(r'^ajax/get_ads/$', 'get_ads'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+\.]+)/$', 'view', name='groups_view'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+\.]+)/delete/(?P<id>\d{1,6})/$', 'delete_role', name='groups_delete_role'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+\.]+)/charter/$', 'charter', name='groups_charter'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+\.]+)/edit/$', 'edit', name='groups_edit'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+\.]+)/gm/$', 'view_gm', name='groups_view_gm'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+\.]+)/gm/edit/$', 'edit_gm', name='groups_edit_gm'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+\.]+)/people/$', 'people', name='groups_people'),
)
