from django.conf.urls import patterns, url
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy

urlpatterns = patterns('ietf.mailtrigger.views',
    url(r'^$', RedirectView.as_view(url=reverse_lazy('mailtrigger_show_triggers'), permanent=True)),
    url(r'^name/$', 'show_triggers',  name='mailtrigger_show_triggers' ),
    url(r'^name/(?P<mailtrigger_slug>[-\w]+)/$', 'show_triggers' ),
    url(r'^recipient/$', 'show_recipients' ),
    url(r'^recipient/(?P<recipient_slug>[-\w]+)/$', 'show_recipients' ),
)
