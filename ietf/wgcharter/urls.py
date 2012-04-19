# Copyright The IETF Trust 2011, All Rights Reserved

from django.conf.urls.defaults import patterns, url
from ietf.doc.models import State

urlpatterns = patterns('django.views.generic.simple',
    url(r'^help/state/$', 'direct_to_template', { 'template': 'wgcharter/states.html', 'extra_context': { 'states': State.objects.filter(type="charter") } }, name='help_charter_states'),
)
urlpatterns += patterns('',
    url(r'^state/$', "ietf.wgcharter.views.change_state", name='charter_change_state'),
    url(r'^(?P<option>initcharter|recharter|abandon)/$', "ietf.wgcharter.views.change_state", name='charter_startstop_process'),
    url(r'^telechat/$', "ietf.wgcharter.views.telechat_date", name='charter_telechat_date'),
    url(r'^(?P<ann>action|review)/$', "ietf.wgcharter.views.announcement_text"),
    url(r'^ballotwriteupnotes/$', "ietf.wgcharter.views.ballot_writeupnotes"),
    url(r'^approve/$', "ietf.wgcharter.views.approve", name='charter_approve'),
    url(r'^submit/$', "ietf.wgcharter.views.submit", name='charter_submit'),

)
