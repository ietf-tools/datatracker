# Copyright The IETF Trust 2008, All Rights Reserved

from django.conf.urls.defaults import patterns, include
from ietf.wginfo import views, edit
from django.views.generic.simple import redirect_to


urlpatterns = patterns('',
     (r'^$', views.wg_dir),
     (r'^summary.txt', redirect_to, { 'url':'/wg/1wg-summary.txt' }),
     (r'^summary-by-area.txt', redirect_to, { 'url':'/wg/1wg-summary.txt' }),
     (r'^summary-by-acronym.txt', redirect_to, { 'url':'/wg/1wg-summary-by-acronym.txt' }),
     (r'^1wg-summary.txt', views.wg_summary_area),
     (r'^1wg-summary-by-acronym.txt', views.wg_summary_acronym),
     (r'^1wg-charters.txt', views.wg_charters),
     (r'^1wg-charters-by-acronym.txt', views.wg_charters_by_acronym),
     (r'^chartering/$', views.chartering_wgs),
     (r'^bofs/$', views.bofs),
     (r'^chartering/create/$', edit.edit, {'action': "charter"}, "wg_create"),
     (r'^bofs/create/$', edit.edit, {'action': "create"}, "bof_create"),
     (r'^(?P<acronym>[a-zA-Z0-9-]+)/documents/txt/$', views.wg_documents_txt),
     (r'^(?P<acronym>[a-zA-Z0-9-]+)/$', views.wg_documents_html, None, "wg_docs"),
     (r'^(?P<acronym>[a-zA-Z0-9-]+)/charter/$', views.wg_charter, None, 'wg_charter'),
     (r'^(?P<acronym>[A-Za-z0-9-]+)/charter/', include('ietf.wgcharter.urls')),
     (r'^(?P<acronym>[a-zA-Z0-9-]+)/history/', views.history),
     (r'^(?P<acronym>[a-zA-Z0-9-]+)/edit/', edit.edit, {'action': "edit"}, "wg_edit"),
     (r'^(?P<acronym>[a-zA-Z0-9-]+)/init-charter/', edit.submit_initial_charter, None, "wg_init_charter"),
     (r'^(?P<acronym>[a-zA-Z0-9-]+)/conclude/', edit.conclude, None, "wg_conclude"),
     (r'^(?P<acronym>[^/]+)/management/', include('ietf.wgchairs.urls')),

)
