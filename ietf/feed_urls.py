from django.conf.urls import patterns
from django.views.generic import RedirectView
from django.conf import settings

from ietf.doc.feeds import DocumentChangesFeed, InLastCallFeed, RfcFeed
from ietf.group.feeds import GroupChangesFeed
from ietf.iesg.feeds import IESGAgendaFeed
from ietf.ipr.feeds import LatestIprDisclosuresFeed
from ietf.liaisons.feeds import LiaisonStatementsFeed
from ietf.meeting.feeds import LatestMeetingMaterialFeed

urlpatterns = patterns(
    '',
    (r'^comments/(?P<remainder>.*)/$', RedirectView.as_view(url='/feed/document-changes/%(remainder)s/', permanent=True)),
    (r'^document-changes/%(name)s/$' % settings.URL_REGEXPS, DocumentChangesFeed()),
    (r'^last-call/$', InLastCallFeed()),
    (r'^group-changes/%(acronym)s/$' % settings.URL_REGEXPS, GroupChangesFeed()),
    (r'^iesg-agenda/$', IESGAgendaFeed()),
    (r'^ipr/$', LatestIprDisclosuresFeed()),
    (r'^liaison/(?P<kind>recent|from|to|subject)/(?:(?P<search>[^/]+)/)?$', LiaisonStatementsFeed()),
    (r'^wg-proceedings/$', LatestMeetingMaterialFeed()),
    (r'^rfc/$', RfcFeed())
)
