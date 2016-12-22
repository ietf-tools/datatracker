from django.conf.urls import url
from django.views.generic import TemplateView

urlpatterns = [
    url(r'^$',  'ietf.release.views.release'),
    url(r'^(?P<version>[0-9.]+.*)/$',  'ietf.release.views.release'),
    url(r'^about/?$',  TemplateView.as_view(template_name='release/about.html')),
    url(r'^todo/?$',  TemplateView.as_view(template_name='release/todo.html')),
]

