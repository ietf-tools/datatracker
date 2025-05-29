# Copyright The IETF Trust 2023-2024, All Rights Reserved

from django.conf import settings

from ietf.api import views_rpc, views_rpc_demo
from ietf.utils.urls import url

urlpatterns = [
    url(r"^doc/drafts/(?P<doc_id>[0-9]+)/$", views_rpc.rpc_draft),
    url(r"^doc/drafts/(?P<doc_id>[0-9]+)/references/$", views_rpc.rpc_draft_refs),
    url(r"^doc/drafts_by_names/$", views_rpc.drafts_by_names),
    url(r"^doc/submitted_to_rpc/$", views_rpc.submitted_to_rpc),
    url(r"^doc/rfc/original_stream/$", views_rpc.rfc_original_stream),
    url(r"^doc/rfc/authors/$", views_rpc.rfc_authors),
    url(r"^doc/draft/authors/$", views_rpc.draft_authors),
    url(r"^person/persons_by_email/$", views_rpc.persons_by_email),
    url(r"^person/(?P<person_id>[0-9]+)/$", views_rpc.rpc_person),
    url(r"^persons/$", views_rpc.rpc_persons),
    url(r"^subject/(?P<subject_id>[0-9]+)/person/$", views_rpc.rpc_subject_person),
]

if settings.SERVER_MODE not in {"production", "test"}:
    # for non production demos
    urlpatterns.append(
        url(r"^doc/create_demo_draft/$", views_rpc_demo.create_demo_draft)
    )
    urlpatterns.append(
        url(r"^person/create_demo_person/$", views_rpc_demo.create_demo_person)
    )
