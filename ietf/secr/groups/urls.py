from django.conf.urls import patterns, url

urlpatterns = patterns('ietf.secr.groups.views',
    url(r'^$', 'search', name='groups'),
    url(r'^add/$', 'add', name='groups_add'),
    url(r'^blue-dot-report/$', 'blue_dot', name='groups_blue_dot'),
    url(r'^search/$', 'search', name='groups_search'),
    #(r'^ajax/get_ads/$', 'get_ads'),
    url(r'^(?P<acronym>[-a-z0-9]+)/$', 'view', name='groups_view'),
    url(r'^(?P<acronym>[-a-z0-9]+)/delete/(?P<id>\d{1,6})/$', 'delete_role', name='groups_delete_role'),
    url(r'^(?P<acronym>[-a-z0-9]+)/charter/$', 'charter', name='groups_charter'),
    url(r'^(?P<acronym>[-a-z0-9]+)/edit/$', 'edit', name='groups_edit'),
    url(r'^(?P<acronym>[-a-z0-9]+)/gm/$', 'view_gm', name='groups_view_gm'),
    url(r'^(?P<acronym>[-a-z0-9]+)/gm/edit/$', 'edit_gm', name='groups_edit_gm'),
    url(r'^(?P<acronym>[-a-z0-9]+)/people/$', 'people', name='groups_people'),
)
