# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns, include, handler404, handler500

from ietf.iesg.feeds import IESGMinutes
from ietf.idtracker.feeds import DocumentComments
from ietf.ipr.feeds import LatestIprDisclosures

from django.conf import settings

feeds = {
    'iesg_minutes': IESGMinutes,
    'comments': DocumentComments,
    'ipr': LatestIprDisclosures,
}

urlpatterns = patterns('',
      (r'^feed/(?P<url>.*)/$', 'django.contrib.syndication.views.feed',
		{ 'feed_dict': feeds}),
      (r'^ann/', include('ietf.announcements.urls')),
      (r'^idtracker/', include('ietf.idtracker.urls')),
      #(r'^my/', include('ietf.my.urls')),
      (r'^drafts/', include('ietf.idindex.urls')),
      (r'^iesg/', include('ietf.iesg.urls')),
      (r'^liaison/', include('ietf.liaisons.urls')),
      (r'^list/', include('ietf.mailinglists.urls')),
      (r'^(?P<path>public|cgi-bin)/', include('ietf.redirects.urls')),
      (r'^ipr/', include('ietf.ipr.urls')),
      (r'^meeting/', include('ietf.meeting.urls')),
      (r'^accounts/', include('ietf.ietfauth.urls')),

      (r'^$', 'ietf.redirects.views.redirect'),

    # Uncomment this for admin:
     (r'^admin/', include('django.contrib.admin.urls')),

     # Uncomment this for review pages:
     (r'^review/$', 'ietf.utils.views.review'),
     (r'^review/all/$', 'ietf.utils.views.all'),
     (r'^review/(?P<page>[0-9a-f]+)/$', 'ietf.utils.views.review'),
     (r'^review/top/(?P<page>[0-9a-f]+)/$', 'ietf.utils.views.top'),

     # Google webmaster tools verification url
     (r'googlea30ad1dacffb5e5b.html', 'django.views.generic.simple.direct_to_template', { 'template': 'googlea30ad1dacffb5e5b.html' })

)

if settings.SERVER_MODE in ('development', 'test'):
    urlpatterns += patterns('',
        (r'^(?P<path>(?:images|css|js)/.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
	)
