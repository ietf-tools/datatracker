# Copyright The IETF Trust 2023-2024, All Rights Reserved

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
    url(r"^draft/by_names/", views_rpc.DraftsByNamesView.as_view()),
    url(r"^doc/rfc/authors/$", views_rpc.rfc_authors),
    url(r"^person/persons_by_email/$", views_rpc.persons_by_email),
    path(r"subject/<str:subject_id>/person/", views_rpc.SubjectPersonView.as_view()),
    path("", include(router.urls)),  # todo get rid of drf prefix when done converting
]
