# Copyright The IETF Trust 2017, All Rights Reserved

from django.conf.urls import include
from django.views.generic import TemplateView

from ietf import api
from ietf.api import views as api_views
from ietf.doc import views_ballot
from ietf.meeting import views as meeting_views
from ietf.submit import views as submit_views
from ietf.utils.urls import url

api.autodiscover()

urlpatterns = [
    # General API help page
    url(r'^$', api_views.api_help),
    # Top endpoint for Tastypie's REST API (this isn't standard Tastypie):
    url(r'^v1/?$', api_views.top_level),
    # For mailarchive use, requires secretariat role
    url(r'^v2/person/person', api_views.ApiV2PersonExportView.as_view()),
    #
    # --- Custom API endpoints, sorted alphabetically ---
    # GPRD: export of personal information for the logged-in person
    url(r'^export/personal-information/$', api_views.PersonalInformationExportView.as_view()),
    # Let IESG members set positions programmatically
    url(r'^iesg/position', views_ballot.api_set_position),
    # Let Meetecho set session video URLs
    url(r'^meeting/session/video/url$', meeting_views.api_set_session_video_url),
    # Let Meetecho trigger recording imports
    url(r'^notify/meeting/import_recordings/(?P<number>[a-z0-9-]+)/?$', meeting_views.api_import_recordings),
    # Let the registration system notify us about registrations
    url(r'^notify/meeting/bluesheet/?$', meeting_views.api_upload_bluesheet),
    # Let the registration system notify us about registrations
    url(r'^notify/meeting/registration/?', api_views.api_new_meeting_registration),
    # OpenID authentication provider
    url(r'^openid/$', TemplateView.as_view(template_name='api/openid-issuer.html'), name='ietf.api.urls.oidc_issuer'),
    url(r'^openid/', include('oidc_provider.urls', namespace='oidc_provider')),
    # Draft submission API
    url(r'^submit/?$', submit_views.api_submit),
    # Datatracker version
    url(r'^version/?$', api_views.version),
]

# Additional (standard) Tastypie endpoints
for n,a in api._api_list:
    urlpatterns += [
        url(r'^v1/', include(a.urls)),
    ]

