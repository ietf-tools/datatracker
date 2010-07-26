# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.meeting import views

urlpatterns = patterns('',
    (r'^(?P<meeting_num>\d+)/materials.html$', views.show_html_materials),
    (r'^agenda/$', views.html_agenda),
    (r'^agenda(?:.html)?$', views.html_agenda),
    (r'^agenda.txt$', views.text_agenda),
    (r'^(?P<num>\d+)/agenda(?:.html)?/?$', views.html_agenda),
    (r'^(?P<num>\d+)/agenda.txt$', views.text_agenda),
    (r'^(?P<num>\d+)/agenda/(?P<session>[A-Za-z0-9-]+)(?P<ext>\.[A-Za-z0-9]+)?$', views.session_agenda),
    (r'^$', views.current_materials),
)

