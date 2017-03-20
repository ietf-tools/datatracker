# Copyright The IETF Trust 2011, All Rights Reserved

from ietf.doc import views_charter, views_doc
from ietf.utils.urls import url

urlpatterns = [
    url(r'^state/$', views_charter.change_state),
    url(r'^title/$', views_charter.change_title),
    url(r'^(?P<option>initcharter|recharter|abandon)/$', views_charter.change_state),
    url(r'^telechat/$', views_doc.telechat_date,                    name='ietf.doc.views_doc.telechat_date;charter'),
    url(r'^notify/$', views_doc.edit_notify,                        name='ietf.doc.views_doc.edit_notify;charter'),
    url(r'^ad/$', views_charter.edit_ad),
    url(r'^action/$', views_charter.action_announcement_text),
    url(r'^review/$', views_charter.review_announcement_text),
    url(r'^ballotwriteupnotes/$', views_charter.ballot_writeupnotes),
    url(r'^approve/$', views_charter.approve),
    url(r'^submit/(?:(?P<option>initcharter|recharter)/)?$', views_charter.submit),
    url(r'^withmilestones-(?P<rev>[0-9-]{2,5}).txt$', views_charter.charter_with_milestones_txt),
]
