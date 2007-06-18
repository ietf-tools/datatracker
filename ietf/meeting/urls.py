from django.conf.urls.defaults import patterns
from ietf.meeting import views

urlpatterns = patterns('',
    (r'^(?P<meeting_num>\d+)/agenda-(?P<html_or_txt>\S+)/$', views.show_html_agenda),
    (r'^(?P<meeting_num>\d+)/materials/$', views.show_html_materials),
)

