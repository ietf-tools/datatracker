from django.conf.urls import patterns, url

urlpatterns = patterns('ietf.secr.roles.views',
    url(r'^$', 'main', name='roles'),
    url(r'^ajax/get-roles/(?P<acronym>[-a-z0-9]+)/$', 'ajax_get_roles', name='roles_ajax_get_roles'),
    url(r'^(?P<acronym>[-a-z0-9]+)/delete/(?P<id>\d{1,6})/$', 'delete_role', name='roles_delete_role'),
)
