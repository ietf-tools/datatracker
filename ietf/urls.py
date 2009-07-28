# Copyright The IETF Trust 2007, 2009, All Rights Reserved

from django.conf.urls.defaults import patterns, include, handler404, handler500

from ietf.iesg.feeds import IESGAgenda
from ietf.idtracker.feeds import DocumentComments, InLastCall
from ietf.ipr.feeds import LatestIprDisclosures
from ietf.proceedings.feeds import LatestWgProceedingsActivity
from ietf.liaisons.feeds import Liaisons

from ietf.idtracker.sitemaps import IDTrackerMap, DraftMap
from ietf.liaisons.sitemaps import LiaisonMap
from ietf.ipr.sitemaps import IPRMap
from ietf.announcements.sitemaps import NOMCOMAnnouncementsMap

from django.conf import settings

feeds = {
    'iesg-agenda': IESGAgenda,
    'last-call': InLastCall,
    'comments': DocumentComments,
    'ipr': LatestIprDisclosures,
    'liaison': Liaisons,
    'wg-proceedings' : LatestWgProceedingsActivity
}

sitemaps = {
    'idtracker': IDTrackerMap,
    'drafts': DraftMap,
    'liaison': LiaisonMap,
    'ipr': IPRMap,
    'nomcom-announcements': NOMCOMAnnouncementsMap,
}

urlpatterns = patterns('',
      (r'^feed/(?P<url>.*)/$', 'django.contrib.syndication.views.feed',
		{ 'feed_dict': feeds}),
      (r'^sitemap.xml$', 'django.contrib.sitemaps.views.index',
		{ 'sitemaps': sitemaps}),
      (r'^sitemap-(?P<section>.+).xml$', 'django.contrib.sitemaps.views.sitemap',
		{'sitemaps': sitemaps}),
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
      (r'^account/', include('ietf.ietfauth.urls')),
      (r'^doc/', include('ietf.idrfc.urls')),
      (r'^wg/', include('ietf.wginfo.urls')),

      (r'^$', 'ietf.redirects.views.redirect'),

     # DJANGO_096: Comment out this line for Django 1.0 -- new admin
     # site works differently, and needs work                       
    # Uncomment this for admin:
     (r'^admin/', include('django.contrib.admin.urls')),

     # Uncomment this for review pages:
     (r'^review/$', 'ietf.utils.views.review'),
     (r'^review/all/$', 'ietf.utils.views.all'),
     (r'^review/(?P<page>[0-9a-f]+)/$', 'ietf.utils.views.review'),
     (r'^review/top/(?P<page>[0-9a-f]+)/$', 'ietf.utils.views.top'),

     # Google webmaster tools verification url
     (r'^googlea30ad1dacffb5e5b.html', 'django.views.generic.simple.direct_to_template', { 'template': 'googlea30ad1dacffb5e5b.html' }),

     # ekr, fluffy, wgcharter tool
#     (r'^wgcharter/', include('ietf.wgcharter.urls')),                       
     
     # Uncomment this for pre-approval tool for initial Internet-Drafts
     #(r'^wg/', include('ietf.wg.urls')),                       

     # Django 0.96 hardcodes /accounts/; we want to use
     # /account/.
     (r'^accounts/(?P<dir>\w+)/', 'django.views.generic.simple.redirect_to', { 'url': '/account/%(dir)s/' }),
)

if settings.SERVER_MODE in ('development', 'test'):
    urlpatterns += patterns('',
        (r'^(?P<path>(?:images|css|js)/.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
	)
