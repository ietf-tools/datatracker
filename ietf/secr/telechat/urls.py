
from ietf.secr.telechat import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.main, name='telechat'),
    url(r'^(?P<date>[0-9\-]+)/bash/$', views.bash, name='telechat_bash'),
    url(r'^(?P<date>[0-9\-]+)/doc/$', views.doc, name='telechat_doc'),
    url(r'^(?P<date>[0-9\-]+)/doc/(?P<name>[A-Za-z0-9.-]+)/$', views.doc_detail, name='telechat_doc_detail'),
    url(r'^(?P<date>[0-9\-]+)/doc/(?P<name>[A-Za-z0-9.-]+)/(?P<nav>next|previous)/$', views.doc_navigate,
        name='telechat_doc_navigate'),
    url(r'^(?P<date>[0-9\-]+)/management/$', views.management, name='telechat_management'),
    url(r'^(?P<date>[0-9\-]+)/minutes/$', views.minutes, name='telechat_minutes'),
    url(r'^(?P<date>[0-9\-]+)/roll-call/$', views.roll_call, name='telechat_roll_call'),
    url(r'^new/$', views.new, name='telechat_new'),
]
