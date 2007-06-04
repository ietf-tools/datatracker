from django.conf.urls.defaults import *
from ietf.meeting import models, views

urlpatterns = patterns('',
    (r'^(?P<meeting_num>\d+)/agenda.(?P<html_or_txt>\S+)$', views.show_html_agenda),
    (r'^(?P<meeting_num>\d+)/materials.html$', views.show_html_materials),
)

