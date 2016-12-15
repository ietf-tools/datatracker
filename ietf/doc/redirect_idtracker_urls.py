from django.conf.urls import patterns
from django.views.generic import RedirectView

urlpatterns = patterns('',
    (r'^help/(?:sub)?state/(?:\d+/)?$', RedirectView.as_view(url='/doc/help/state/draft-iesg/')),
    (r'^help/evaluation/$', RedirectView.as_view(url='https://www.ietf.org/iesg/voting-procedures.html')),
    (r'^status/$', RedirectView.as_view(url='/doc/iesg/')),
    (r'^status/last-call/$', RedirectView.as_view(url='/doc/iesg/last-call/')),
    (r'^rfc0*(?P<rfc_number>\d+)/$', RedirectView.as_view(url='/doc/rfc%(rfc_number)s/')),
    (r'^(?P<name>[^/]+)/$', RedirectView.as_view(url='/doc/%(name)s/')),
    (r'^(?P<name>[^/]+)/comment/\d+/$', RedirectView.as_view(url='/doc/%(name)s/history/')),
    (r'^$', RedirectView.as_view(url='/doc/')),
)
