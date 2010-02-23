# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf import settings
from django.conf.urls.defaults import patterns
from ietf.idtracker.models import InternetDraft
from ietf.idindex import views
from ietf.idindex.views import alphabet, orgs

info_dict = {
    'queryset': InternetDraft.objects.all(),
    'template_name': 'idindex/internetdraft_detail.html',
    'extra_context': {
	'alphabet': alphabet,
	'orgs': orgs,
    }
}

urlpatterns = patterns('',
     (r'^wgid/(?P<id>\d+)/$', views.wgdocs_redir),
     (r'^wg/(?P<wg>[^/]+)/$', views.wgdocs),
     (r'^all/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/all/'}),
     (r'^rfc/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/all/#rfc'}),
     (r'^dead/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/all/#dead'}),
     (r'^current/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/active/'}),
     (r'^(?P<id>\d+)/related/$', views.redirect_related),
     (r'^(?P<slug>[^/]+)/related/$', views.view_related_docs),
     (r'^(?P<object_id>\d+)/$', views.redirect_id),
     (r'^(?P<slug>[^/]+)/$', views.view_id, dict(info_dict, slug_field='filename')),
     (r'^all_id(?:_txt)?.html$', 'django.views.generic.simple.redirect_to', { 'url': 'http://www.ietf.org/id/all_id.txt' }),
     (r'^$', views.search),
)

if settings.SERVER_MODE != 'production':
    urlpatterns += patterns('',
        (r'^_test/all_id.txt$', views.test_all_id_txt),                        
        (r'^_test/id_index.txt$', views.test_id_index_txt), 
        (r'^_test/id_abstracts.txt$', views.test_id_abstracts_txt)   
    )
