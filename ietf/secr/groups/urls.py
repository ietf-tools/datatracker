from django.conf import settings

from ietf.secr.groups import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.search),
    url(r'^blue-dot-report/$', views.blue_dot),
    #(r'^ajax/get_ads/$', views.get_ads),
    url(r'^%(acronym)s/$' % settings.URL_REGEXPS, views.view),
    url(r'^%(acronym)s/delete/(?P<id>\d{1,6})/$' % settings.URL_REGEXPS, views.delete_role),
    url(r'^%(acronym)s/charter/$' % settings.URL_REGEXPS, views.charter),
    url(r'^%(acronym)s/people/$' % settings.URL_REGEXPS, views.people),
]
