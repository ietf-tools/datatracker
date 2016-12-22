from django.conf.urls import url

urlpatterns = [
    url(r'^$', 'ietf.secr.telechat.views.main', name='telechat'),
    url(r'^(?P<date>[0-9\-]+)/bash/$', 'ietf.secr.telechat.views.bash', name='telechat_bash'),
    url(r'^(?P<date>[0-9\-]+)/doc/$', 'ietf.secr.telechat.views.doc', name='telechat_doc'),
    url(r'^(?P<date>[0-9\-]+)/doc/(?P<name>[A-Za-z0-9.-]+)/$', 'ietf.secr.telechat.views.doc_detail', name='telechat_doc_detail'),
    url(r'^(?P<date>[0-9\-]+)/doc/(?P<name>[A-Za-z0-9.-]+)/(?P<nav>next|previous)/$', 'ietf.secr.telechat.views.doc_navigate',
        name='telechat_doc_navigate'),
    url(r'^(?P<date>[0-9\-]+)/management/$', 'ietf.secr.telechat.views.management', name='telechat_management'),
    url(r'^(?P<date>[0-9\-]+)/minutes/$', 'ietf.secr.telechat.views.minutes', name='telechat_minutes'),
    url(r'^(?P<date>[0-9\-]+)/roll-call/$', 'ietf.secr.telechat.views.roll_call', name='telechat_roll_call'),
    url(r'^new/$', 'ietf.secr.telechat.views.new', name='telechat_new'),
]
