# Copyright The IETF Trust 2011, All Rights Reserved

from django.conf.urls import patterns, url
from django.conf import settings

urlpatterns = patterns('',
    url(r'^state/$', "ietf.doc.views_charter.change_state", name='charter_change_state'),
    url(r'^title/$', "ietf.doc.views_charter.change_title", name='charter_change_title'),
    url(r'^(?P<option>initcharter|recharter|abandon)/$', "ietf.doc.views_charter.change_state", name='charter_startstop_process'),
    url(r'^telechat/$', "ietf.doc.views_doc.telechat_date", name='charter_telechat_date'),
    url(r'^notify/$', "ietf.doc.views_doc.edit_notify", name='charter_edit_notify'),
    url(r'^ad/$', "ietf.doc.views_charter.edit_ad", name='charter_edit_ad'),
    url(r'^action/$', "ietf.doc.views_charter.action_announcement_text"),
    url(r'^review/$', "ietf.doc.views_charter.review_announcement_text"),
    url(r'^ballotwriteupnotes/$', "ietf.doc.views_charter.ballot_writeupnotes"),
    url(r'^approve/$', "ietf.doc.views_charter.approve", name='charter_approve'),
    url(r'^submit/(?:(?P<option>initcharter|recharter)/)?$', "ietf.doc.views_charter.submit", name='charter_submit'),
    url(r'^withmilestones-%(rev)s.txt$' % settings.URL_REGEXPS, "ietf.doc.views_charter.charter_with_milestones_txt", name='charter_with_milestones_txt'),
)
