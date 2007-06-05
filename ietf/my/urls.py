from django.conf.urls.defaults import patterns
from ietf.my import views

urlpatterns = patterns('',
     # this is for testing
     (r'^(?P<addr>.+)/$', views.my),
     (r'^$', views.my),
)
