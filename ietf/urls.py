from django.conf.urls.defaults import patterns, include, handler404, handler500

from ietf.iesg.feeds import IESGMinutes
from ietf.idtracker.feeds import DocumentComments
from ietf.ipr.feeds import LatestIprDisclosures
import ietf.utils.views
import ietf.views

from django.conf import settings

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

     # Uncomment this for review pages:
     (r'^review/$', 'ietf.utils.views.review'),
     (r'^review/all/$', 'ietf.utils.views.all'),
     (r'^review/(?P<page>[0-9]+)/$', 'ietf.utils.views.review'),
     (r'^review/top/(?P<page>[0-9]+)/$', 'ietf.utils.views.top'),

)

if settings.SERVER_MODE in ('development', 'test'):
    urlpatterns += patterns('',
        (r'^(?P<path>(?:images|css|js)/.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
	)
