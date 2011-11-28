from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template
from django.views.generic import list_detail
from sec.rolodex import views

urlpatterns = patterns('sec.rolodex.views',
    url(r'^$', 'search', name='rolodex'),
    url(r'^add/$', 'add', name='rolodex_add'),
    #url(r'^add-confirm/$', direct_to_template, {'template': 'rolodex/add_confirm.html'}, name='rolodex_add_confirm'),
    url(r'^add-proceed/$', 'add_proceed', name='rolodex_add_proceed'),
    url(r'^(?P<id>\d{1,6})/edit/$', 'edit', name='rolodex_edit'),
    #url(r'^(?P<id>\d{1,6})/delete/$', 'delete', name='rolodex_delete'),
    url(r'^(?P<id>\d{1,6})/$', 'view', name='rolodex_view'),
)
