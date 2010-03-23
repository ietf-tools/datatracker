# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf import settings
from django.conf.urls.defaults import patterns
from ietf.idindex import views

urlpatterns = patterns('',
     (r'^$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/'}),
     (r'^all/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/all/'}),
     (r'^rfc/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/all/#rfc'}),
     (r'^dead/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/all/#dead'}),
     (r'^current/$', 'django.views.generic.simple.redirect_to', { 'url': '/doc/active/'}),
     (r'^(?P<object_id>\d+)/(related/)?$', views.redirect_id),
     (r'^(?P<filename>[^/]+)/(related/)?$', views.redirect_filename),
     (r'^wgid/(?P<id>\d+)/$', views.wgdocs_redirect_id),
     (r'^wg/(?P<acronym>[^/]+)/$', views.wgdocs_redirect_acronym),
     (r'^all_id(?:_txt)?.html$', 'django.views.generic.simple.redirect_to', { 'url': 'http://www.ietf.org/id/all_id.txt' }),
)

if settings.SERVER_MODE != 'production':
    urlpatterns += patterns('',
        (r'^_test/all_id.txt$', views.test_all_id_txt),                        
        (r'^_test/all_id2.txt$', views.test_all_id2_txt),
        (r'^_test/id_index.txt$', views.test_id_index_txt), 
        (r'^_test/id_abstracts.txt$', views.test_id_abstracts_txt)   
    )
