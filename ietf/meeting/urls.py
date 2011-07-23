# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.meeting import views

urlpatterns = patterns('',
    (r'^(?P<meeting_num>\d+)/materials.html$', views.show_html_materials),
    (r'^agenda/$', views.html_agenda),
    (r'^agenda(?:.html)?$', views.html_agenda),
    (r'^requests.html$', views.meeting_requests),
    (r'^agenda.txt$', views.text_agenda),
    (r'^agenda/agenda.ics$', views.ical_agenda),
    (r'^agenda.ics$', views.ical_agenda),
    (r'^agenda.csv$', views.csv_agenda),
    (r'^agenda/week-view.html$', views.week_view),
    (r'^week-view.html$', views.week_view),
    (r'^(?P<num>\d+)/agenda(?:.html)?/?$', views.html_agenda),
    (r'^(?P<num>\d+)/requests.html$', views.meeting_requests),
    (r'^(?P<num>\d+)/agenda.txt$', views.text_agenda),
    (r'^(?P<num>\d+)/agenda.ics$', views.ical_agenda),
    (r'^(?P<num>\d+)/agenda.csv$', views.csv_agenda),
    (r'^(?P<num>\d+)/week-view.html$', views.week_view),
    (r'^(?P<num>\d+)/agenda/(?P<session>[A-Za-z0-9-]+)-drafts.pdf$', views.session_draft_pdf),
    (r'^(?P<num>\d+)/agenda/(?P<session>[A-Za-z0-9-]+)-drafts.tgz$', views.session_draft_tarfile),
    (r'^(?P<num>\d+)/agenda/(?P<session>[A-Za-z0-9-]+)(?P<ext>\.[A-Za-z0-9]+)?$', views.session_agenda),
    (r'^$', views.current_materials),
)

