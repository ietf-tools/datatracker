from django.conf.urls import url
from django.conf import settings

from ietf.secr.roles import views

urlpatterns = [
    url(r'^$', views.main, name='roles'),
    url(r'^ajax/get-roles/%(acronym)s/$' % settings.URL_REGEXPS, views.ajax_get_roles, name='roles_ajax_get_roles'),
    url(r'^%(acronym)s/delete/(?P<id>\d{1,6})/$' % settings.URL_REGEXPS, views.delete_role, name='roles_delete_role'),
]
