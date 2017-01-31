from django.conf.urls import url
from django.conf import settings

urlpatterns = [
    url(r'^$', 'ietf.secr.groups.views.search', name='groups'),
    url(r'^add/$', 'ietf.secr.groups.views.add', name='groups_add'),
    url(r'^blue-dot-report/$', 'ietf.secr.groups.views.blue_dot', name='groups_blue_dot'),
    url(r'^search/$', 'ietf.secr.groups.views.search', name='groups_search'),
    #(r'^ajax/get_ads/$', 'ietf.secr.groups.views.get_ads'),
    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, 'ietf.secr.groups.views.view', name='groups_view'),
    url(r'^%(acronym)s/delete/(?P<id>\d{1,6})/$' % settings.URL_REGEXPS, 'ietf.secr.groups.views.delete_role', name='groups_delete_role'),
    url(r'^%(acronym)s/charter/$' % settings.URL_REGEXPS, 'ietf.secr.groups.views.charter', name='groups_charter'),
    url(r'^%(acronym)s/edit/$' % settings.URL_REGEXPS, 'ietf.secr.groups.views.edit', name='groups_edit'),
    url(r'^%(acronym)s/gm/$' % settings.URL_REGEXPS, 'ietf.secr.groups.views.view_gm', name='groups_view_gm'),
    url(r'^%(acronym)s/gm/edit/$' % settings.URL_REGEXPS, 'ietf.secr.groups.views.edit_gm', name='groups_edit_gm'),
    url(r'^%(acronym)s/people/$' % settings.URL_REGEXPS, 'ietf.secr.groups.views.people', name='groups_people'),
]
