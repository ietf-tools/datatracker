from django.conf.urls import url
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy

urlpatterns = [
    url(r'^$', RedirectView.as_view(url=reverse_lazy('mailtrigger_show_triggers'), permanent=True)),
    url(r'^name/$', 'ietf.mailtrigger.views.show_triggers',  name='mailtrigger_show_triggers' ),
    url(r'^name/(?P<mailtrigger_slug>[-\w]+)/$', 'ietf.mailtrigger.views.show_triggers' ),
    url(r'^recipient/$', 'ietf.mailtrigger.views.show_recipients' ),
    url(r'^recipient/(?P<recipient_slug>[-\w]+)/$', 'ietf.mailtrigger.views.show_recipients' ),
]
