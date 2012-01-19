from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template
from django.views.generic import list_detail

from sec.groups import views

urlpatterns = patterns('sec.groups.views',
    url(r'^$', 'search', name='groups'),
    url(r'^add/$', 'add', name='groups_add'),
    url(r'^search/$', 'search', name='groups_search'),
    url(r'^(?P<name>[A-Za-z0-9._\-\+]+)/$', 'view', name='groups_view'),
    url(r'^(?P<name>[A-Za-z0-9._\-\+]+)/description/$', 'description', name='groups_description'),
    url(r'^(?P<name>[A-Za-z0-9._\-\+]+)/edit/$', 'edit', name='groups_edit'),
    url(r'^(?P<name>[A-Za-z0-9._\-\+]+)/gm/$', 'view_gm', name='groups_view_gm'),
    url(r'^(?P<name>[A-Za-z0-9._\-\+]+)/gm/edit/$', 'edit_gm', name='groups_edit_gm'),
    url(r'^(?P<name>[A-Za-z0-9._\-\+]+)/people/$', 'people', name='groups_people'),
    url(r'^(?P<name>[A-Za-z0-9._\-\+]+)/people/delete/$', 'delete', name='groups_people_delete'),
    #(r'^get_ads/$', 'sec.groups.views.get_ads'),
    #(r'^list/(?P<id>\d{1,6})/$', 'sec.groups.views.grouplist'),
    
)
