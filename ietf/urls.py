# Copyright The IETF Trust 2007-2022, All Rights Reserved

from django.conf import settings
from django.conf.urls.static import static as static_url
from django.contrib import admin
from django.contrib.sitemaps import views as sitemap_views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import HttpResponse
from django.urls import include, path
from django.views import static as static_view
from django.views.generic import TemplateView
from django.views.defaults import server_error

import debug                            # pyflakes:ignore

from ietf.doc import views_search
from ietf.group.urls import group_urls, grouptype_urls, stream_urls
from ietf.ipr.sitemaps import IPRMap
from ietf.liaisons.sitemaps import LiaisonMap
from ietf.utils.urls import url


# sometimes, this code gets called more than once, which is an
# that seems impossible to work around.
try:
    admin.site.disable_action('delete_selected')
except KeyError:
    pass

sitemaps = {
    'liaison': LiaisonMap,
    'ipr': IPRMap,
}

urlpatterns = [
    url(r'^$', views_search.frontpage),
    url(r'^health/', lambda _: HttpResponse()),
    url(r'^accounts/', include('ietf.ietfauth.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^admin/docs/', include('django.contrib.admindocs.urls')),
    url(r'^ann/', include('ietf.nomcom.redirect_ann_urls')),
    url(r'^api/', include('ietf.api.urls')),
    url(r'^community/', include('ietf.community.urls')),
    url(r'^accounts/settings/', include('ietf.cookies.urls')),
    url(r'^doc/', include('ietf.doc.urls')),
    url(r'^drafts/', include('ietf.doc.redirect_drafts_urls')),
    url(r'^mailtrigger/',include('ietf.mailtrigger.urls')),
    url(r'^feed/', include('ietf.feed_urls')),
    url(r'^group/', include(group_urls)),
    url(r'^help/', include('ietf.help.urls')),
    url(r'^idtracker/', include('ietf.doc.redirect_idtracker_urls')),
    url(r'^iesg/', include('ietf.iesg.urls')),
    url(r'^ipr/', include('ietf.ipr.urls')),
    url(r'^liaison/', include('ietf.liaisons.urls')),
    url(r'^list/', include('ietf.mailinglists.urls')),
    url(r'^meeting/', include('ietf.meeting.urls')),
    url(r'^nomcom/', include('ietf.nomcom.urls')),
    url(r'^person/', include('ietf.person.urls')),
    url(r'^release/', include('ietf.release.urls')),
    url(r'^secr/', include('ietf.secr.urls')),
    url(r'^sitemap-(?P<section>.+).xml$', sitemap_views.sitemap, {'sitemaps': sitemaps}),
    url(r'^sitemap.xml$', sitemap_views.index, { 'sitemaps': sitemaps}),
    url(r'^stats/', include('ietf.stats.urls')),
    url(r'^status/', include('ietf.status.urls')),
    url(r'^stream/', include(stream_urls)),
    url(r'^submit/', include('ietf.submit.urls')),
    url(r'^sync/', include('ietf.sync.urls')),
    url(r'^templates/', include('ietf.dbtemplate.urls')),
    url(r'^(?P<group_type>(wg|rg|ag|rag|team|dir|review|area|program|iabasg|iabworkshop|adhoc|ise|adm|rfcedtyp|edwg|edappr))/', include(grouptype_urls)),

    # Redirects
    url(r'^(?P<path>public)/', include('ietf.redirects.urls')),

    # Google webmaster tools verification url
    url(r'^googlea30ad1dacffb5e5b.html', TemplateView.as_view(template_name='googlea30ad1dacffb5e5b.html')),

    # Android webmanifest
    url(r'^site.webmanifest', TemplateView.as_view(template_name='site.webmanifest'), name='site.webmanifest'),
]

# This is needed to serve files during testing
if settings.SERVER_MODE in ('development', 'test'):
    save_debug = settings.DEBUG
    settings.DEBUG = True
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += [
            url(r'^_test500/$', server_error), #utils_views.exception),
            ## maybe preserve some static legacy URLs ?
            url(r'^(?P<path>(?:images|css|js)/.*)$', static_view.serve, {'document_root': settings.STATIC_ROOT+'ietf/'}),
        ]
    urlpatterns += static_url(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    settings.DEBUG = save_debug

# Debug Toolbar
if getattr(settings, 'USE_DEBUG_TOOLBAR', False):
    try:
        import debug_toolbar
        urlpatterns = urlpatterns + [path('__debug__/', include(debug_toolbar.urls)), ]
    except ImportError:
        pass
