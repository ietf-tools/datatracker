
from ietf.secr.telechat import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.main),
    url(r'^(?P<date>[0-9\-]+)/bash/$', views.bash),
    url(r'^(?P<date>[0-9\-]+)/doc/$', views.doc),
    url(r'^(?P<date>[0-9\-]+)/doc/(?P<name>[A-Za-z0-9.-]+)/$', views.doc_detail),
    url(r'^(?P<date>[0-9\-]+)/doc/(?P<name>[A-Za-z0-9.-]+)/(?P<nav>next|previous)/$', views.doc_navigate),
    url(r'^(?P<date>[0-9\-]+)/management/$', views.management),
    url(r'^(?P<date>[0-9\-]+)/minutes/$', views.minutes),
    url(r'^(?P<date>[0-9\-]+)/roll-call/$', views.roll_call),
]
