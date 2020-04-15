# Copyright The IETF Trust 2017, All Rights Reserved

from django.conf.urls import include

from ietf import api
from ietf.api import views as api_views
from ietf.doc import views_ballot
from ietf.meeting import views as meeting_views
from ietf.submit import views as submit_views
from ietf.utils.urls import url

api.autodiscover()

urlpatterns = [
    # Top endpoint for Tastypie's REST API (this isn't standard Tastypie):
    url(r'^$', api_views.api_help),
    url(r'^v1/?$', api_views.top_level),
    # Custom API endpoints
    url(r'^notify/meeting/import_recordings/(?P<number>[a-z0-9-]+)/?$', meeting_views.api_import_recordings),
    url(r'^meeting/session/video/url$', meeting_views.api_set_session_video_url),
    url(r'^submit/?$', submit_views.api_submit),
    url(r'^iesg/position', views_ballot.api_set_position),
    # GPRD: export of personal information for the logged-in person
    url(r'^export/personal-information/$', api_views.PersonalInformationExportView.as_view()),
    # For mailarchive use, requires secretariat role
    url(r'^v2/person/person', api_views.ApiV2PersonExportView.as_view()),
    # For meetecho access
    url(r'^v2/person/access/meetecho', api_views.PersonAccessMeetechoView.as_view()),
]

# Additional (standard) Tastypie endpoints
for n,a in api._api_list:
    urlpatterns += [
        url(r'^v1/', include(a.urls)),
    ]

