# Copyright The IETF Trust 2016-2019, All Rights Reserved
from django.conf import settings

from ietf.doc import views_review
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views_review.request_review),
    url(r'^(?P<request_id>[0-9]+)/$', views_review.review_request),
    url(r'^(?P<request_id>[0-9]+)/login/$', views_review.review_request_forced_login),
    url(r'^(?P<request_id>[0-9]+)/close/$', views_review.close_request),
    url(r'^(?P<request_id>[0-9]+)/assignreviewer/$', views_review.assign_reviewer),
    url(r'^(?P<assignment_id>[0-9]+)/rejectreviewerassignment/$', views_review.reject_reviewer_assignment),
    url(r'^(?P<assignment_id>[0-9]+)/complete/$', views_review.complete_review),
    url(r'^%(acronym)s/submitunsolicitedreview/$' % settings.URL_REGEXPS, views_review.complete_review),
    url(r'^submitunsolicitedreview/$', views_review.submit_unsolicited_review_choose_team),
    url(r'^(?P<assignment_id>[0-9]+)/withdraw/$', views_review.withdraw_reviewer_assignment),
    url(r'^(?P<assignment_id>[0-9]+)/noresponse/$', views_review.mark_reviewer_assignment_no_response),
    url(r'^assignment/(?P<assignment_id>[0-9]+)/searchmailarchive/$', views_review.search_mail_archive),
    url(r'^team/%(acronym)s/searchmailarchive/$' % settings.URL_REGEXPS, views_review.search_mail_archive),
    url(r'^(?P<request_id>[0-9]+)/editcomment/$', views_review.edit_comment),
    url(r'^(?P<request_id>[0-9]+)/editdeadline/$', views_review.edit_deadline),
    url(r'^addreviewwish/$', views_review.review_wish_add),
    url(r'^removereviewwishes/$', views_review.review_wishes_remove),
]
