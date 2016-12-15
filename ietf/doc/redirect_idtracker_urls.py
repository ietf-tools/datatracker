from django.conf.urls import patterns
from django.views.generic import RedirectView

urlpatterns = patterns('',
    (r'^help/(?:sub)?state/(?:\d+/)?$', RedirectView.as_view(url='/doc/help/state/draft-iesg/', permanent=True)),
    (r'^help/evaluation/$', RedirectView.as_view(url='https://www.ietf.org/iesg/voting-procedures.html', permanent=True)),
    (r'^status/$', RedirectView.as_view(url='/doc/iesg/', permanent=True)),
    (r'^status/last-call/$', RedirectView.as_view(url='/doc/iesg/last-call/', permanent=True)),
    (r'^rfc0*(?P<rfc_number>\d+)/$', RedirectView.as_view(url='/doc/rfc%(rfc_number)s/', permanent=True)),
    (r'^(?P<name>[^/]+)/$', RedirectView.as_view(url='/doc/%(name)s/', permanent=True)),
    (r'^(?P<name>[^/]+)/comment/\d+/$', RedirectView.as_view(url='/doc/%(name)s/history/', permanent=True)),
    (r'^$', RedirectView.as_view(url='/doc/', permanent=True)),
)
