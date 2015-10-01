from django.conf.urls import patterns, url
from django.conf import settings

urlpatterns = patterns('ietf.secr.roles.views',
    url(r'^$', 'main', name='roles'),
    url(r'^ajax/get-roles/%(acronym)s/$' % settings.URL_REGEXPS, 'ajax_get_roles', name='roles_ajax_get_roles'),
    url(r'^%(acronym)s/delete/(?P<id>\d{1,6})/$' % settings.URL_REGEXPS, 'delete_role', name='roles_delete_role'),
)
