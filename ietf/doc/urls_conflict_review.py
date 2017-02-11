
from ietf.doc import views_conflict_review, views_doc
from ietf.utils.urls import url

urlpatterns = [
    url(r'^state/$',                 views_conflict_review.change_state,  name='conflict_review_change_state'),
    url(r'^submit/$',                views_conflict_review.submit,        name='conflict_review_submit'),
    url(r'^ad/$',                    views_conflict_review.edit_ad,       name='conflict_review_ad'),
    url(r'^approve/$',               views_conflict_review.approve,       name='conflict_review_approve'),
    url(r'^start_conflict_review/$', views_conflict_review.start_review,  name='conflict_review_start'),
    url(r'^telechat/$',              views_doc.telechat_date, name='conflict_review_telechat_date'),
    url(r'^notices/$',               views_doc.edit_notify,  name='conflict_review_notices'),
]


