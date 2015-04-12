from django.conf.urls import patterns
from django.views.generic import TemplateView

urlpatterns = patterns('',
    (r'^$',  'ietf.release.views.release'),
    (r'^(?P<version>[0-9.]+.*)/$',  'ietf.release.views.release'),
    (r'^about/?$',  TemplateView.as_view(template_name='release/about.html')),
    (r'^todo/?$',  TemplateView.as_view(template_name='release/todo.html')),

)

