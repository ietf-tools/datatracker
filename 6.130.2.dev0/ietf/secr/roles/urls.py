from django.conf import settings

from ietf.secr.roles import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.main),
    url(r'^ajax/get-roles/%(acronym)s/$' % settings.URL_REGEXPS, views.ajax_get_roles),
    url(r'^%(acronym)s/delete/(?P<id>\d{1,6})/$' % settings.URL_REGEXPS, views.delete_role),
]
