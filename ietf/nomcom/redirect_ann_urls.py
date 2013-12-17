from django.conf.urls.defaults import patterns
from django.views.generic.simple import redirect_to

urlpatterns = patterns('',
     (r'^nomcom/$', 'django.views.generic.simple.redirect_to', { 'url': "/nomcom/ann/", 'permanent': True }),
     (r'^nomcom/(?P<message_id>\d+)/$', 'django.views.generic.simple.redirect_to', { 'url': "/nomcom/ann/%(message_id)s/", 'permanent': True }),
)
