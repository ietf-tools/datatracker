# Copyright The IETF Trust 2023, All Rights Reserved

from ietf.api import views_rpc

from ietf.utils.urls import url

urlpatterns = [
    url(r'^doc/create_demo_draft/$', views_rpc.create_demo_draft),
    url(r'^doc/drafts/(?P<doc_id>[0-9]+)$', views_rpc.rpc_draft),
    url(r'^doc/submitted_to_rpc/$', views_rpc.submitted_to_rpc),
    url(r'^person/create_demo_person/$', views_rpc.create_demo_person),
    url(r'^person/(?P<person_id>[0-9]+)$', views_rpc.rpc_person),
    url(r'^persons/$', views_rpc.rpc_persons),
]
