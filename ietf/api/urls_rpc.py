# Copyright The IETF Trust 2023-2026, All Rights Reserved
from django.urls import include, path

from ietf.api import views_rpc
from ietf.api.routers import PrefixedDefaultRouter
from ietf.utils.urls import url

router = PrefixedDefaultRouter(use_regex_path=False, name_prefix="ietf.api.purple_api")
router.include_format_suffixes = False
router.register(r"draft", views_rpc.DraftViewSet, basename="draft")
router.register(r"person", views_rpc.PersonViewSet)
router.register(r"rfc", views_rpc.RfcViewSet, basename="rfc")

router.register(
    r"rfc/<int:rfc_number>/authors",
    views_rpc.RfcAuthorViewSet,
    basename="rfc-authors",
)

urlpatterns = [
    url(r"^doc/drafts_by_names/", views_rpc.DraftsByNamesView.as_view()),
    url(r"^persons/search/", views_rpc.RpcPersonSearch.as_view()),
    path(
        r"rfc/publish/",
        views_rpc.RfcPubNotificationView.as_view(),
        name="ietf.api.purple_api.notify_rfc_published",
    ),
    path(
        r"rfc/publish/files/",
        views_rpc.RfcPubFilesView.as_view(),
        name="ietf.api.purple_api.upload_rfc_files",
    ),
    path(r"subject/<str:subject_id>/person/", views_rpc.SubjectPersonView.as_view()),
]

# add routers at the end so individual routes can steal parts of their address
# space (specifically, ^person/ routes so far)
urlpatterns.extend(
    [
        path("", include(router.urls)),
    ]
)
