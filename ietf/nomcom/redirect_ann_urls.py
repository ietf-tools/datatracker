from django.conf.urls import url
from django.views.generic import RedirectView

urlpatterns = [
    url(r'^nomcom/$', RedirectView.as_view(url="/nomcom/ann/", permanent=True)),
    url(r'^nomcom/(?P<message_id>\d+)/$', RedirectView.as_view(url="/nomcom/ann/%(message_id)s/", permanent=True)),
]
