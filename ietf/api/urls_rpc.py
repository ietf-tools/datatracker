# Copyright The IETF Trust 2023-2025, All Rights Reserved

from rest_framework import routers

from django.conf import settings
from django.urls import include, path

from ietf.api import views_rpc, views_rpc_demo
from ietf.utils.urls import url

router = routers.DefaultRouter(use_regex_path=False)
router.include_format_suffixes = False
router.register(r"draft", views_rpc.DraftViewSet, basename="draft")
router.register(r"person", views_rpc.PersonViewSet)
router.register(r"rfc", views_rpc.RfcViewSet, basename="rfc")

router.register(
    r"rfc/<int:rfc_number>/authors",
    views_rpc.RfcAuthorViewSet,
    basename="rfc-authors",
)

if settings.SERVER_MODE not in {"production", "test"}:
    # for non production demos
    router.register(r"demo", views_rpc_demo.DemoViewSet, basename="demo")


urlpatterns = [
    url(r"^doc/drafts_by_names/", views_rpc.DraftsByNamesView.as_view()),
    url(r"^persons/search/", views_rpc.RpcPersonSearch.as_view()),
    path(r"subject/<str:subject_id>/person/", views_rpc.SubjectPersonView.as_view()),
]

# add routers at the end so individual routes can steal parts of their address
# space (specifically, ^person/ routes so far)
urlpatterns.extend(
    [
        path("", include(router.urls)),
    ]
)
