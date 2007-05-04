from django.conf.urls.defaults import *
from ietf.idtracker.models import InternetDraft
from ietf.idindex import views
from ietf.idindex import forms
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
     (r'^wgdocs/(?P<id>\d+)/$', views.wgdocs),
     (r'^wgdocs/(?P<slug>[^/]+)/$', views.wgdocs),
     (r'^wglist/(?P<wg>[^/]+)/$', views.wglist),
     (r'^inddocs/(?P<filter>[^/]+)/$', views.inddocs),
     (r'^otherdocs/(?P<cat>[^/]+)/$', views.otherdocs),
     (r'^showdocs/(?P<cat>[^/]+)/((?P<sortby>[^/]+)/)?$', views.showdocs),
     (r'^(?P<object_id>\d+)/$', 'django.views.generic.list_detail.object_detail', info_dict),
     (r'^(?P<slug>[^/]+)/$', 'django.views.generic.list_detail.object_detail', dict(info_dict, slug_field='filename')),
     (r'^all_id_txt.html$', views.all_id, { 'template_name': 'idindex/all_id_txt.html' }),
     (r'^all_id.html$', views.all_id, { 'template_name': 'idindex/all_id.html' }),
     (r'^$', views.search),
)
