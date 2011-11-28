from django.conf.urls.defaults import *

urlpatterns = patterns('sec.telechat.views',
    url(r'^$', 'main', name='telechat'),
    url(r'^doc/(?P<name>[A-Za-z0-9.-]+)/$', 'doc', name='telechat_doc'),
    url(r'^doc/(?P<name>[A-Za-z0-9.-]+)/(?P<nav>next|previous)/$', 'doc_navigate', name='telechat_doc_navigate'),
    url(r'^group/(?P<id>[A-Za-z0-9.-]+)/$', 'group', name='telechat_group'),
)
