# Copyright The IETF Trust 2011, All Rights Reserved

from django.conf.urls import url
from django.conf import settings

from ietf.doc import views_charter, views_doc

urlpatterns = [
    url(r'^state/$', views_charter.change_state, name='charter_change_state'),
    url(r'^title/$', views_charter.change_title, name='charter_change_title'),
    url(r'^(?P<option>initcharter|recharter|abandon)/$', views_charter.change_state, name='charter_startstop_process'),
    url(r'^telechat/$', views_doc.telechat_date, name='charter_telechat_date'),
    url(r'^notify/$', views_doc.edit_notify, name='charter_edit_notify'),
    url(r'^ad/$', views_charter.edit_ad, name='charter_edit_ad'),
    url(r'^action/$', views_charter.action_announcement_text),
    url(r'^review/$', views_charter.review_announcement_text),
    url(r'^ballotwriteupnotes/$', views_charter.ballot_writeupnotes),
    url(r'^approve/$', views_charter.approve, name='charter_approve'),
    url(r'^submit/(?:(?P<option>initcharter|recharter)/)?$', views_charter.submit, name='charter_submit'),
    url(r'^withmilestones-%(rev)s.txt$' % settings.URL_REGEXPS, views_charter.charter_with_milestones_txt, name='charter_with_milestones_txt'),
]
