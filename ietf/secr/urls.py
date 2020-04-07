from django.conf.urls import url, include
from django.views.generic import TemplateView

urlpatterns = [
    url(r'^$', TemplateView.as_view(template_name='main.html')),
    url(r'^announcement/', include('ietf.secr.announcement.urls')),
    url(r'^areas/', include('ietf.secr.areas.urls')),
    url(r'^console/', include('ietf.secr.console.urls')),
    url(r'^groups/', include('ietf.secr.groups.urls')),
    url(r'^meetings/', include('ietf.secr.meetings.urls')),
    url(r'^proceedings/', include('ietf.secr.proceedings.urls')),
    url(r'^roles/', include('ietf.secr.roles.urls')),
    url(r'^rolodex/', include('ietf.secr.rolodex.urls')),
    url(r'^sreq/', include('ietf.secr.sreq.urls')),
    url(r'^telechat/', include('ietf.secr.telechat.urls')),
]
