# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from ietf.doc import views_conflict_review, views_doc
from ietf.utils.urls import url

urlpatterns = [
    url(r'^state/$',                 views_conflict_review.change_state),
    url(r'^submit/$',                views_conflict_review.submit),
    url(r'^ad/$',                    views_conflict_review.edit_ad),
    url(r'^approve/$',               views_conflict_review.approve_conflict_review),
    url(r'^start_conflict_review/$', views_conflict_review.start_review),
    url(r'^telechat/$',              views_doc.telechat_date,               name='ietf.doc.views_doc.telechat_date;conflict-review'),
    url(r'^notices/$',               views_doc.edit_notify,                 name='ietf.doc.views_doc.edit_notify;conflict-review'),
]


