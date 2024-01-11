# Copyright The IETF Trust 2024, All Rights Reserved

from django.db import migrations

DESCRIPTION = (
    "The Web and Internet Transport (WIT) area covers protocols that provide "
    "the functions of the Transport Layer of the Internet, such as QUIC, TCP, "
    "UDP, SCTP, and DCCP, including congestion control and queue management.  "
    "It also has responsibility for protocols that implement the World Wide Web "
    "(like HTTP) and adjacent technologies."
)


def forward(apps, schema_editor):
    Group = apps.get_model("group", "Group")

    wit = Group.objects.create(
        acronym="wit",
        charter=None,
        name="Web and Internet Transport Area",
        state_id="active",
        type_id="area",
        parent_id=2,  # The IESG group
        description=DESCRIPTION,
        list_email="",
        list_subscribe="",
        list_archive="",
        comments="",
        meeting_seen_as_area=False,
        # No unused states
        # No unused tags
        used_roles="[]",
        uses_milestone_dates=False,
    )
    ops = Group.objects.get(acronym="ops")
    int_area = Group.objects.get(acronym="int")  # int is reserved
    sec = Group.objects.get(acronym="sec")

    Group.objects.filter(
        acronym__in=[
            "avtcore",
            "cdni",
            "ccwg",
            "core",
            "httpapi",
            "httpbis",
            "masque",
            "moq",
            "nfsv4",
            "quic",
            "rtcweb",
            "taps",
            "tcpm",
            "tsvarea",
            "tsvwg",
            "webtrans",
        ]
    ).update(parent=wit)
    Group.objects.filter(acronym__in=["alto", "ippm"]).update(parent=ops)
    Group.objects.filter(acronym="dtn").update(parent=int_area)
    Group.objects.filter(acronym__in=["scim", "tigress"]).update(parent=sec)


def reverse(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    art = Group.objects.get(acronym="art")
    tsv = Group.objects.get(acronym="tsv")
    Group.objects.filter(
        acronym__in=[
            "avtcore",
            "cdni",
            "core",
            "httpapi",
            "httpbis",
            "moq",
            "rtcweb",
            "scim",
            "tigress",
            "webtrans",
        ]
    ).update(parent=art)
    Group.objects.filter(
        acronym__in=[
            "alto",
            "ccwg",
            "dtn",
            "ippm",
            "masque",
            "nfsv4",
            "quic",
            "taps",
            "tcpm",
            "tsvarea",
            "tsvwg",
        ]
    ).update(parent=tsv)
    Group.objects.filter(acronym="wit").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("group", "0004_modern_list_archive"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
