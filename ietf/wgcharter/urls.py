# Copyright The IETF Trust 2011, All Rights Reserved

from django.conf.urls.defaults import patterns, url
from ietf.wgcharter import views, views_search, views_edit, views_ballot, views_submit
from ietf.doc.models import State

urlpatterns = patterns('django.views.generic.simple',
    url(r'^help/state/$', 'direct_to_template', { 'template': 'wgcharter/states.html', 'extra_context': { 'states': State.objects.filter(type="charter") } }, name='help_charter_states'),
)
urlpatterns += patterns('',
    url(r'^create/$', views_edit.edit_info, name="wg_create"),
    (r'^searchPerson/$', views.search_person), # FIXME: fix URL
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/((?P<rev>[0-9][0-9](-[0-9][0-9])?)/)?((?P<tab>ballot|writeup|history)/)?$', views.wg_main, name="wg_view"),
    (r'^(?P<name>[A-Za-z0-9._+-]+)/_ballot.data$', views.wg_ballot),
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/edit/state/$', views_edit.change_state, name='wg_change_state'),
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/edit/(?P<option>initcharter|recharter|abandon)/$', views_edit.change_state, name='wg_startstop_process'),
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/edit/telechat/$', views_edit.telechat_date, name='charter_telechat_date'),
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/edit/info/$', views_edit.edit_info, name='wg_edit_info'),
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/edit/conclude/$', views_edit.conclude, name='wg_conclude'),
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/edit/(?P<ann>action|review)/$', views_ballot.announcement_text, name='wg_announcement_text'),
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/edit/position/$', views_ballot.edit_position, name='wg_edit_position'),
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/edit/sendballotcomment/$', views_ballot.send_ballot_comment, name='wg_send_ballot_comment'),
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/edit/ballotwriteupnotes/$', views_ballot.ballot_writeupnotes, name='wg_ballot_writeupnotes'),
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/edit/approveballot/$', views_ballot.approve_ballot, name='wg_approve_ballot'),
    url(r'^(?P<name>[A-Za-z0-9._+-]+)/submit/$', views_submit.submit, name='wg_submit'),

)
