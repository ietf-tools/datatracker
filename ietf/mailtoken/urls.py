from django.conf.urls import patterns, url
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy

urlpatterns = patterns('ietf.mailtoken.views',
    url(r'^$', RedirectView.as_view(url=reverse_lazy('mailtoken_show_tokens'), permanent=True)),
    url(r'^token/$', 'show_tokens',  name='mailtoken_show_tokens' ),
    url(r'^token/(?P<mailtoken_slug>[-\w]+)/$', 'show_tokens' ),
    url(r'^recipient/$', 'show_recipients' ),
    url(r'^recipient/(?P<recipient_slug>[-\w]+)/$', 'show_recipients' ),
)
