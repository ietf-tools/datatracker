from django.conf.urls import patterns, url
from ietf.doc import views_review

urlpatterns = patterns('',
    url(r'^$', views_review.request_review),
    url(r'^(?P<request_id>[0-9]+)/$', views_review.review_request),
    url(r'^(?P<request_id>[0-9]+)/close/$', views_review.close_request),
    url(r'^(?P<request_id>[0-9]+)/assignreviewer/$', views_review.assign_reviewer),
    url(r'^(?P<request_id>[0-9]+)/rejectreviewerassignment/$', views_review.reject_reviewer_assignment),
    url(r'^(?P<request_id>[0-9]+)/complete/$', views_review.complete_review),
    url(r'^(?P<request_id>[0-9]+)/searchmailarchive/$', views_review.search_mail_archive),
)

