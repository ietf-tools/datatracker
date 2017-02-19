from django.views.generic import RedirectView

from ietf.utils.urls import url

urlpatterns = [
    url(r'^help/(?:sub)?state/(?:\d+/)?$', RedirectView.as_view(url='/doc/help/state/draft-iesg/', permanent=True)),
    url(r'^help/evaluation/$', RedirectView.as_view(url='https://www.ietf.org/iesg/voting-procedures.html', permanent=True)),
    url(r'^status/$', RedirectView.as_view(url='/doc/iesg/', permanent=True)),
    url(r'^status/last-call/$', RedirectView.as_view(url='/doc/iesg/last-call/', permanent=True)),
    url(r'^rfc0*(?P<rfc_number>\d+)/$', RedirectView.as_view(url='/doc/rfc%(rfc_number)s/', permanent=True)),
    url(r'^(?P<name>[^/]+)/$', RedirectView.as_view(url='/doc/%(name)s/', permanent=True)),
    url(r'^(?P<name>[^/]+)/comment/\d+/$', RedirectView.as_view(url='/doc/%(name)s/history/', permanent=True)),
    url(r'^$', RedirectView.as_view(url='/doc/', permanent=True)),
]
