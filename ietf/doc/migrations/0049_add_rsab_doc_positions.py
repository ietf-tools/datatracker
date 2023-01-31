# Copyright The IETF Trust 2022, All Rights Reserved
# -*- coding: utf-8 -*-

from django.db import migrations


def forward(apps, schema_editor):
    State = apps.get_model("doc", "State")
    State.objects.create(
        type_id="draft-stream-editorial",
        slug="rsab_review",
        name="RSAB Review",
        desc="RSAB Review",
        used=True,
    )
    BallotPositionName = apps.get_model("name", "BallotPositionName")
    BallotPositionName.objects.create(slug="concern", name="Concern", blocking=True)

    BallotType = apps.get_model("doc", "BallotType")
    bt = BallotType.objects.create(
        doc_type_id="draft",
        slug="rsab-approve",
        name="RSAB Approve",
        question="Is this draft ready for publication in the Editorial stream?",
    )
    bt.positions.set(
        ["yes", "concern", "recuse"]
    )  # See RFC9280 section 3.2.2 list item 9.


def reverse(apps, schema_editor):
    State = apps.get_model("doc", "State")
    State.objects.filter(type_id="draft-stream-editorial", slug="rsab_review").delete()

    Position = apps.get_model("name", "BallotPositionName")
    Position.objects.filter(slug="concern").delete()

    BallotType = apps.get_model("doc", "BallotType")
    BallotType.objects.filter(slug="irsg-approve").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("doc", "0048_allow_longer_notify"),
        ("name", "0045_polls_and_chatlogs"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
