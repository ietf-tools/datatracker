from django.conf.urls import patterns, url
from django.conf import settings

urlpatterns = patterns('ietf.secr.groups.views',
    url(r'^$', 'search', name='groups'),
    url(r'^add/$', 'add', name='groups_add'),
    url(r'^blue-dot-report/$', 'blue_dot', name='groups_blue_dot'),
    url(r'^search/$', 'search', name='groups_search'),
    #(r'^ajax/get_ads/$', 'get_ads'),
    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, 'view', name='groups_view'),
    url(r'^%(acronym)s/delete/(?P<id>\d{1,6})/$' % settings.URL_REGEXPS, 'delete_role', name='groups_delete_role'),
    url(r'^%(acronym)s/charter/$' % settings.URL_REGEXPS, 'charter', name='groups_charter'),
    url(r'^%(acronym)s/edit/$' % settings.URL_REGEXPS, 'edit', name='groups_edit'),
    url(r'^%(acronym)s/gm/$' % settings.URL_REGEXPS, 'view_gm', name='groups_view_gm'),
    url(r'^%(acronym)s/gm/edit/$' % settings.URL_REGEXPS, 'edit_gm', name='groups_edit_gm'),
    url(r'^%(acronym)s/people/$' % settings.URL_REGEXPS, 'people', name='groups_people'),
)
