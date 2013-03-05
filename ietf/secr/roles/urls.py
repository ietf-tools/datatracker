from django.conf.urls.defaults import *

urlpatterns = patterns('ietf.secr.roles.views',
    url(r'^$', 'main', name='roles'),
    url(r'^ajax/get-roles/(?P<acronym>[A-Za-z0-9_\-\+\.]+)/$', 'ajax_get_roles', name='roles_ajax_get_roles'),
    url(r'^(?P<acronym>[A-Za-z0-9_\-\+\.]+)/delete/(?P<id>\d{1,6})/$', 'delete_role', name='roles_delete_role'),
)
