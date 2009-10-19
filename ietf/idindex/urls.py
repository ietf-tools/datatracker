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
     (r'^ind/(?P<filter>[^/]+)/$', views.inddocs),
     (r'^other/(?P<cat>[^/]+)/$', views.otherdocs),
     # (?P<cat>(?:all|rfc|current|dead)) really confuses reverse()
     (r'^(?P<cat>all)/$', views.showdocs),
     (r'^(?P<cat>rfc)/$', views.showdocs),
     (r'^(?P<cat>current)/$', views.showdocs),
     (r'^(?P<cat>dead)/$', views.showdocs),
     (r'^(?P<id>\d+)/related/$', views.redirect_related),
     (r'^(?P<slug>[^/]+)/related/$', views.view_related_docs),
     (r'^(?P<object_id>\d+)/$', views.redirect_id),
     (r'^(?P<slug>[^/]+)/$', views.view_id, dict(info_dict, slug_field='filename')),
     (r'^all_id_txt.html$', views.all_id, { 'template_name': 'idindex/all_id_txt.html' }),
     (r'^all_id.html$', views.all_id, { 'template_name': 'idindex/all_id.html' }),
     (r'^$', views.search),
)

if settings.SERVER_MODE != 'production':
    urlpatterns += patterns('',
        (r'^_test/all_id.txt$', views.test_all_id_txt),                        
        (r'^_test/id_index.txt$', views.test_id_index_txt), 
        (r'^_test/id_abstracts.txt$', views.test_id_abstracts_txt)   
    )
