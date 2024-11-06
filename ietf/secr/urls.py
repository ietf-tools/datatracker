from django.urls import re_path, include
from django.views.generic import TemplateView

urlpatterns = [
    re_path(r'^$', TemplateView.as_view(template_name='index.html'), name='ietf.secr'),
    re_path(r'^announcement/', include('ietf.secr.announcement.urls')),
    re_path(r'^meetings/', include('ietf.secr.meetings.urls')),
    re_path(r'^rolodex/', include('ietf.secr.rolodex.urls')),
    re_path(r'^sreq/', include('ietf.secr.sreq.urls')),
    re_path(r'^telechat/', include('ietf.secr.telechat.urls')),
]
