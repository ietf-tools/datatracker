from django.conf.urls import patterns, url
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy

urlpatterns = patterns('ietf.eventmail.views',
    url(r'^$', RedirectView.as_view(url=reverse_lazy('eventmail_show_patterns'), permanent=True)),
    url(r'^event/$', 'show_patterns',  name='eventmail_show_patterns' ),
    url(r'^event/(?P<eventmail_slug>[-\w]+)/$', 'show_patterns' ),
    url(r'^recipient/$', 'show_ingredients' ),
    url(r'^recipient/(?P<ingredient_slug>[-\w]+)/$', 'show_ingredients' ),
)
