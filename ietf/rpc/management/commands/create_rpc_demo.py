# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...factories import RpcPersonFactory


class Command(BaseCommand):
    help = "Populate data for RPC Tools Refresh demo"
    
    def handle(self, *args, **options):
        # Refuse to run in production
        if settings.SERVER_MODE == "production":
            raise CommandError("This command is not allowed in production mode")

        
        # From "Manage Team Members" wireframe
        RpcPersonFactory(
            person__name="A. Travis",
            can_hold_role=["formatting", "first_editor", "final_review_editor"],
            capable_of=["codecomp-abnf", "clusters-beginner", "ianaconsid-beginner"],
        )
        RpcPersonFactory(
            person__name="B. Jenkins",
            can_hold_role=["formatting", "first_editor", "second_editor", "final_review_editor", "publisher", "manager"],
            capable_of=["codecomp-abnf", "code-comp-xml", "codecomp-yang", "clusters-expert", "ianaconsid-intermediate"],
        )
        RpcPersonFactory(
            person__name="C. Brown",
            can_hold_role=["formatting"],
            capable_of=["clusters-beginner"],
        )
        RpcPersonFactory(
            person__name="C. Simmons",
            can_hold_role=["formatting", "first_editor", "second_editor", "final_review_editor"],
            capable_of=["codecomp-abnf", "codecomp-mib", "clusters-intermediate", "ianaconsid-beginner"],
        )
        RpcPersonFactory(
            person__name="F. Fermat",
            can_hold_role=["formatting", "first_editor", "second_editor", "final_review_editor", "publisher"],
            capable_of=["codecomp-yang", "clusters-intermediate", "ianaconsid-beginner"],
        )
        RpcPersonFactory(
            person__name="K. Strawberry",
            can_hold_role=["formatting", "first_editor"],
            capable_of=["ianaconsid-beginner"],
        )
        RpcPersonFactory(
            person__name="O. Bleu",
            can_hold_role=["formatting", "first_editor", "second_editor", "final_review_editor"],
            capable_of=["codecomp-abnf", "codecomp-xml", "codecomp-yang", "clusters-expert", "ianaconsid-intermediate"],
        )
        RpcPersonFactory(
            person__name="Patricia Parker",
            can_hold_role=["formatting", "first_editor", "second_editor", "final_review_editor"],
            capable_of=["codecomp-abnf", "codecomp-xml", "codecomp-yang", "clusters-expert", "ianaconsid-expert"],
        )
        RpcPersonFactory(
            person__name="S. Bexar",
            can_hold_role=["formatting", "first_editor", "second_editor", "final_review_editor", "publisher"],
            capable_of=["codecomp-abnf", "codecomp-mib", "codecomp-xml", "clusters-expert", "ianaconsid-expert"],
        )
        RpcPersonFactory(
            person__name="T. Langfeld",
            can_hold_role=["formatting", "first_editor"],
            capable_of=["ianaconsid-beginner"],
        )
        RpcPersonFactory(
            person__name="U. Garrison",
            can_hold_role=["formatting"],
            capable_of=[],  # was "formatting" but we did not create that Capability
        )
