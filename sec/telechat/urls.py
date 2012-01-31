from django.conf.urls.defaults import *

urlpatterns = patterns('sec.telechat.views',
    url(r'^$', 'main', name='telechat'),
    url(r'^(?P<date>[0-9\-]+)/bash/$', 'bash', name='telechat_bash'),
    url(r'^(?P<date>[0-9\-]+)/doc/$', 'doc', name='telechat_doc'),
    url(r'^(?P<date>[0-9\-]+)/doc/(?P<name>[A-Za-z0-9.-]+)/$', 'doc_detail', name='telechat_doc_detail'),
    url(r'^(?P<date>[0-9\-]+)/doc/(?P<name>[A-Za-z0-9.-]+)/(?P<nav>next|previous)/$', 'doc_navigate',
        name='telechat_doc_navigate'),
    url(r'^(?P<date>[0-9\-]+)/management/$', 'management', name='telechat_management'),
    url(r'^(?P<date>[0-9\-]+)/minutes/$', 'minutes', name='telechat_minutes'),
    url(r'^(?P<date>[0-9\-]+)/roll-call/$', 'roll_call', name='telechat_roll_call'),
    url(r'^(?P<date>[0-9\-]+)/group/(?P<acronym>[A-Za-z0-9_\-\+]+)/$', 'group', name='telechat_group'),
    url(r'^(?P<date>[0-9\-]+)/group/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<nav>next|previous)/$', 'group_navigate',
        name='telechat_group_navigate'),
    url(r'^new/$', 'new', name='telechat_new'),
)
