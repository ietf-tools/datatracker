# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.announcements.models import Announcement

from django.conf import settings

nomcom_dict = {
    'queryset': Announcement.objects.all().filter(nomcom=True)
    }

urlpatterns = patterns('',
#    (r'^nomcom/$', 'django.views.generic.simple.redirect_to', {'url': 'http://www.ietf.org/nomcom/index.html'} ),
    (r'^nomcom/$', 'ietf.announcements.views.nomcom'),
    (r'^nomcom/(?P<object_id>\d+)/$', 'ietf.announcements.views.message_detail') if settings.USE_DB_REDESIGN_PROXY_CLASSES else (r'^nomcom/(?P<object_id>\d+)/$', 'django.views.generic.list_detail.object_detail', nomcom_dict)
)
