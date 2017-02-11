from django.conf import settings

from ietf.secr.groups import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.search, name='groups'),
    url(r'^add/$', views.add, name='groups_add'),
    url(r'^blue-dot-report/$', views.blue_dot, name='groups_blue_dot'),
    url(r'^search/$', views.search, name='groups_search'),
    #(r'^ajax/get_ads/$', views.get_ads),
    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, views.view, name='groups_view'),
    url(r'^%(acronym)s/delete/(?P<id>\d{1,6})/$' % settings.URL_REGEXPS, views.delete_role, name='groups_delete_role'),
    url(r'^%(acronym)s/charter/$' % settings.URL_REGEXPS, views.charter, name='groups_charter'),
    url(r'^%(acronym)s/edit/$' % settings.URL_REGEXPS, views.edit, name='groups_edit'),
    url(r'^%(acronym)s/gm/$' % settings.URL_REGEXPS, views.view_gm, name='groups_view_gm'),
    url(r'^%(acronym)s/gm/edit/$' % settings.URL_REGEXPS, views.edit_gm, name='groups_edit_gm'),
    url(r'^%(acronym)s/people/$' % settings.URL_REGEXPS, views.people, name='groups_people'),
]
