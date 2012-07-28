from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('ietf.doc.views_conflict_review',
    url(r'^state/$',                 "change_state",  name='conflict_review_change_state'),
    url(r'^submit/$',                "submit",        name='conflict_review_submit'),
    url(r'^notices/$',               "edit_notices",  name='conflict_review_notices'),
    url(r'^ad/$',                    "edit_ad",       name='conflict_review_ad'),
    url(r'^approve/$',               "approve",       name='conflict_review_approve'),
    url(r'^start_conflict_review/$', "start_review",  name='conflict_review_start'),
    url(r'^telechat/$',              "telechat_date", name='conflict_review_telechat_date'),
)

