# Copyright The IETF Trust 2024, All Rights Reserved

from django.db import migrations

DESCRIPTION = (
    "The Web and Internet Transport (WIT) area covers protocols that provide "
    "the functions of the Transport Layer of the Internet, such as QUIC, TCP, "
    "UDP, SCTP, and DCCP, including congestion control and queue management.  "
    "It also has responsibility for protocols that implement the World Wide Web "
    "(like HTTP) and adjacent technologies."
)


def move_to_area(Group, acronyms, area):
    for group in Group.objects.filter(acronym__in=acronyms):
        e = group.groupevent_set.create(
            by_id=1,
            type="info_changed",
            desc=f"Moved group from {group.parent.acronym} to {area.acronym}",
        )
        group.parent = area
        group.time = e.time
        group.save()  # Creates a GroupHistory object


def undo_move_to_area(Group, acronyms, area_to_restore):
    for group in Group.objects.filter(acronym__in=acronyms):
        e = group.groupevent_set.filter(
            desc=f"Moved group from {area_to_restore.acronym} to {group.parent.acronym}"
        ).last()
        group.history_set.filter(time__gte=e.time).delete()
        e.delete()
    Group.objects.filter(acronym__in=acronyms).update(parent=area_to_restore)


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
    wit.groupevent_set.create(
        by_id=1,
        type="info_changed",
        desc="Created area",
    )
    ops = Group.objects.get(acronym="ops")
    int_area = Group.objects.get(acronym="int")  # int is reserved
    sec = Group.objects.get(acronym="sec")

    move_to_area(
        Group,
        [
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
        ],
        wit,
    )
    move_to_area(Group, ["alto", "ippm"], ops)
    move_to_area(Group, ["dtn"], int_area)
    move_to_area(Group, ["scim", "tigress"], sec)
    witarea = Group.objects.create(
        acronym="witarea",
        charter=None,
        name="Web and Internet Transport Area Open Meeting",
        state_id="active",
        type_id="ag",
        parent=wit,
        description="",
        list_email="witarea@ietf.org",
        list_subscribe="https://www.ietf.org/mailman/listinfo/witarea",
        list_archive="https://mailarchive.ietf.org/arch/browse/witarea/",
        comments="",
        meeting_seen_as_area=False,
        # No unused states
        # No unused tags
        used_roles="[]",
        uses_milestone_dates=False,
    )
    witarea.groupevent_set.create(
        by_id=1,
        type="info_changed",
        desc="Created group",
    )


def reverse(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    art = Group.objects.get(acronym="art")
    tsv = Group.objects.get(acronym="tsv")
    undo_move_to_area(
        Group,
        [
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
        ],
        art,
    )
    undo_move_to_area(
        Group,
        [
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
        ],
        tsv,
    )
    Group.objects.filter(acronym="witarea").delete()
    Group.objects.filter(acronym="wit").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("group", "0004_modern_list_archive"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
