from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import redirect_to
from sec.roles import views


urlpatterns = patterns('sec.roles.views',
    #url(r'^$', redirect_to, {'url': 'iab/'}, name='roles'),
    url(r'^$', 'main', name='roles'),
    url(r'^ajax/get-roles/(?P<acronym>[A-Za-z0-9_\-\+\.]+)/$', 'ajax_get_roles', name='roles_ajax_get_roles'),
    url(r'^delete/(?P<type>ietf|iab|nomcom)/(?P<id>\d{1,6})/$', 'delete_role', name='roles_delete_role'),
    url(r'^liaisons/$', 'liaisons', name='roles_liaisons'),
    url(r'^(?P<type>iab|ietf|nomcom)/$', 'chair', name='roles_chair'),
)
