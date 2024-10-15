# Copyright The IETF Trust 2023, All Rights Reserved

from rest_framework import routers
from django.urls import include, path

from ietf.api import views_rpc

from ietf.utils.urls import url

router = routers.DefaultRouter()
router.register(r"drafts", views_rpc.DraftViewSet)
router.register(r"person", views_rpc.PersonViewSet)

urlpatterns = [
    url(r"^doc/create_demo_draft/$", views_rpc.create_demo_draft),
    url(r"^doc/drafts_by_names/", views_rpc.DraftsByNamesView.as_view()),
    url(r"^doc/rfc/original_stream/$", views_rpc.rfc_original_stream),
    url(r"^person/create_demo_person/$", views_rpc.create_demo_person),
    url(r"^persons/$", views_rpc.RpcPersonsView.as_view()),
    path(r"subject/<str:subject_id>/person/", views_rpc.SubjectPersonView.as_view()),
    path("drf/", include(router.urls)),  # todo get rid of drf prefix when done converting
]
