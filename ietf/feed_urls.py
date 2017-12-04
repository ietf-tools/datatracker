from django.views.generic import RedirectView
from django.conf import settings

from ietf.doc.feeds import DocumentChangesFeed, InLastCallFeed, RfcFeed
from ietf.group.feeds import GroupChangesFeed
from ietf.iesg.feeds import IESGAgendaFeed
from ietf.ipr.feeds import LatestIprDisclosuresFeed
from ietf.liaisons.feeds import LiaisonStatementsFeed
from ietf.meeting.feeds import LatestMeetingMaterialFeed
from ietf.utils.urls import url

urlpatterns = [ 
    url(r'^comments/(?P<remainder>.*)/$', RedirectView.as_view(url='/feed/document-changes/%(remainder)s/', permanent=True)),
    url(r'^document-changes/%(name)s/$' % settings.URL_REGEXPS, DocumentChangesFeed()),
    url(r'^last-call/$', InLastCallFeed()),
    url(r'^group-changes/%(acronym)s/$' % settings.URL_REGEXPS, GroupChangesFeed()),
    url(r'^iesg-agenda/$', IESGAgendaFeed()),
    url(r'^ipr/$', LatestIprDisclosuresFeed()),
    url(r'^liaison/(?P<kind>recent|from|to|subject)/(?:(?P<search>[^/]+)/)?$', LiaisonStatementsFeed()),
    url(r'^wg-proceedings/$', LatestMeetingMaterialFeed()),
    url(r'^rfc/(?P<year>\d{4})/?$', RfcFeed()),
    url(r'^rfc/$', RfcFeed()),
]
