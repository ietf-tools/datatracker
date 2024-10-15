# Copyright The IETF Trust 2023, All Rights Reserved

from rest_framework import routers
from django.urls import include, path

from ietf.api import views_rpc

from ietf.utils.urls import url

router = routers.DefaultRouter()
router.register(r"demo", views_rpc.DemoViewSet, basename="demo")
router.register(r"draft", views_rpc.DraftViewSet, basename="draft")
router.register(r"person", views_rpc.PersonViewSet)
router.register(r"rfc", views_rpc.RfcViewSet, basename="rfc")

urlpatterns = [
    url(r"^doc/create_demo_draft/$", views_rpc.create_demo_draft),
    url(r"^doc/drafts_by_names/", views_rpc.DraftsByNamesView.as_view()),
    url(r"^persons/$", views_rpc.RpcPersonsView.as_view()),
    path(r"subject/<str:subject_id>/person/", views_rpc.SubjectPersonView.as_view()),
    path("drf/", include(router.urls)),  # todo get rid of drf prefix when done converting
]
