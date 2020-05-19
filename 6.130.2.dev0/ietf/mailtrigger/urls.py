from django.views.generic import RedirectView
from django.urls import reverse_lazy

from ietf.mailtrigger import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', RedirectView.as_view(url=reverse_lazy('ietf.mailtrigger.views.show_triggers'), permanent=True)),
    url(r'^name/$', views.show_triggers),
    url(r'^name/(?P<mailtrigger_slug>[-\w]+)/$', views.show_triggers ),
    url(r'^recipient/$', views.show_recipients ),
    url(r'^recipient/(?P<recipient_slug>[-\w]+)/$', views.show_recipients ),
]
