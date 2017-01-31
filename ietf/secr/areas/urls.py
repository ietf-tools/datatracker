from django.conf.urls import url

urlpatterns = [
    url(r'^$', 'ietf.secr.areas.views.list_areas', name='areas'),
    url(r'^add/$', 'ietf.secr.areas.views.add', name='areas_add'),
    url(r'^getemails', 'ietf.secr.areas.views.getemails', name='areas_emails'),
    url(r'^getpeople', 'ietf.secr.areas.views.getpeople', name='areas_getpeople'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/$', 'ietf.secr.areas.views.view', name='areas_view'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/edit/$', 'ietf.secr.areas.views.edit', name='areas_edit'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/people/$', 'ietf.secr.areas.views.people', name='areas_people'),
    url(r'^(?P<name>[A-Za-z0-9.-]+)/people/modify/$', 'ietf.secr.areas.views.modify', name='areas_modify'),
]
