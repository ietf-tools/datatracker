from django.conf.urls import patterns
from django.views.generic import RedirectView

urlpatterns = patterns('',
    (r'^nomcom/$', RedirectView.as_view(url="/nomcom/ann/", permanent=True)),
    (r'^nomcom/(?P<message_id>\d+)/$', RedirectView.as_view(url="/nomcom/ann/%(message_id)s/", permanent=True)),
)
