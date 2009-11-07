# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.idtracker.models import Area, IETFWG
from ietf.mailinglists.models import NonWgMailingList

urlpatterns = patterns('django.views.generic.list_detail',
     (r'^area/$', 'object_list', { 'queryset': Area.objects.filter(status=1).select_related().order_by('acronym.acronym'), 'template_name': 'mailinglists/areas_list.html' }),
     (r'^nonwg/$', 'object_list', { 'queryset': NonWgMailingList.objects.filter(status__gt=0) }),
     (r'wg/$', 'object_list', { 'queryset': IETFWG.objects.filter(email_archive__startswith='http'), 'template_name': 'mailinglists/wgwebmail_list.html' }),
)
urlpatterns += patterns('',
     (r'^nonwg/update/$', 'django.views.generic.simple.redirect_to', { 'url': 'http://datatracker.ietf.org/list/nonwg/'}),
     (r'^request/$', 'django.views.generic.simple.redirect_to', { 'url': 'http://www.ietf.org/list/request.html' }),
)
