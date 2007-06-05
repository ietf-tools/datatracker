from django.conf.urls.defaults import patterns, include

from ietf.iesg.feeds import IESGMinutes
from ietf.idtracker.feeds import DocumentComments
from ietf.ipr.feeds import LatestIprDisclosures
import ietf.views

feeds = {
    'iesg_minutes': IESGMinutes,
    'comments': DocumentComments,
    'ipr': LatestIprDisclosures,
}

urlpatterns = patterns('',
      (r'^feeds/(?P<url>.*)/$', 'django.contrib.syndication.views.feed',
		{ 'feed_dict': feeds}),
      (r'^announcements/', include('ietf.announcements.urls')),
      (r'^idtracker/', include('ietf.idtracker.urls')),
      (r'^my/', include('ietf.my.urls')),
      (r'^idindex/', include('ietf.idindex.urls')),
      (r'^iesg/', include('ietf.iesg.urls')),
      (r'^liaisons/', include('ietf.liaisons.urls')),
      (r'^mailinglists/', include('ietf.mailinglists.urls')),
      (r'^(?P<path>public|cgi-bin)/', include('ietf.redirects.urls')),
      (r'^ipr/', include('ietf.ipr.urls')),
      (r'^meeting/', include('ietf.meeting.urls')),
      (r'^accounts/', include('ietf.ietfauth.urls')),

      (r'^$', ietf.views.apps),

    # Uncomment this for admin:
     (r'^admin/', include('django.contrib.admin.urls')),
)
