# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.announcements.models import Announcement

nomcom_dict = {
    'queryset': Announcement.objects.all().filter(nomcom=True)
}

urlpatterns = patterns('',
#    (r'^nomcom/$', 'django.views.generic.simple.redirect_to', {'url': 'http://www.ietf.org/nomcom/index.html'} ),
    (r'^nomcom/$', 'ietf.announcements.views.nomcom'),
    (r'^nomcom/chairs/', 'ietf.announcements.views.nomcom_chairs'),
    (r'^nomcom/(?P<object_id>\d+)/$', 'django.views.generic.list_detail.object_detail', nomcom_dict)
)
