# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    GroupFeatures = apps.get_model("group", "GroupFeatures")
    GroupTypeName = apps.get_model("name", "GroupTypeName")

    GroupTypeName.objects.create(
        slug="edwg",
        name="Editorial Stream Working Group",
        desc="Editorial Stream Working Group",
        used=True,
    )
    GroupTypeName.objects.create(
        slug="edappr",
        name="Editorial Stream Approval Group",
        desc="Editorial Stream Approval Group",
        used=True,
    )
    Group.objects.filter(acronym="rswg").update(type_id="edwg")
    Group.objects.filter(acronym="rsab").update(type_id="edappr")
    Group.objects.filter(acronym="editorial").delete()
    GroupFeatures.objects.create(
        type_id="edwg",
        need_parent=False,
        has_milestones=False,
        has_chartering_process=False,
        has_documents=True,
        has_session_materials=True,
        has_meetings=True,
        has_reviews=False,
        has_default_chat=True,
        acts_like_wg=True,
        create_wiki=False,
        custom_group_roles=False,
        customize_workflow=True,
        is_schedulable=True,
        show_on_agenda=True,
        agenda_filter_type_id="normal",
        req_subm_approval=True,
        agenda_type_id="ietf",
        about_page="ietf.group.views.group_about",
        default_tab="ietf.group.views.group_documents",
        material_types=["slides"],
        default_used_roles=["chair"],
        admin_roles=["chair"],
        docman_roles=["chair"],
        groupman_roles=["chair"],
        groupman_authroles=["Secretariat"],
        matman_roles=["chair"],
        role_order=["chair"],
        session_purposes=["regular"],
    )
    # Create edappr GroupFeature
    GroupFeatures.objects.create(
        type_id="edappr",
        need_parent=False,
        has_milestones=False,
        has_chartering_process=False,
        has_documents=False,
        has_session_materials=True,
        has_meetings=True,
        has_reviews=False,
        has_default_chat=True,
        acts_like_wg=False,
        create_wiki=False,
        custom_group_roles=False,
        customize_workflow=False,
        is_schedulable=True,
        show_on_agenda=True,
        agenda_filter_type_id="normal",
        req_subm_approval=False,
        agenda_type_id="ietf",
        about_page="ietf.group.views.group_about",
        default_tab="ietf.group.views.group_about",
        material_types=["slides"],
        default_used_roles=["chair", "member"],
        admin_roles=["chair"],
        docman_roles=["chair"],
        groupman_roles=["chair"],
        groupman_authroles=["Secretariat"],
        matman_roles=["chair"],
        role_order=["chair", "member"],
        session_purposes=["officehourse", "regular"],
    )
    GroupFeatures.objects.filter(type_id="editorial").delete()
    GroupTypeName.objects.filter(slug="editorial").delete()


def reverse(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    GroupFeatures = apps.get_model("group", "GroupFeatures")
    GroupTypeName = apps.get_model("name", "GroupTypeName")
    GroupTypeName.objects.filter(slug="editorial").update(name="Editorial")
    Group.objects.create(
        acronym="editorial",
        name="Editorial Stream",
        state_id="active",
        type_id="editorial",
        parent=None,
    )
    GroupFeatures.objects.create(
        type_id="editorial",
        need_parent=False,
        has_milestones=False,
        has_chartering_process=False,
        has_documents=False,
        has_session_materials=False,
        has_meetings=False,
        has_reviews=False,
        has_default_chat=False,
        acts_like_wg=False,
        create_wiki=False,
        custom_group_roles=True,
        customize_workflow=False,
        is_schedulable=False,
        show_on_agenda=False,
        agenda_filter_type_id="none",
        req_subm_approval=False,
        agenda_type_id="side",
        about_page="ietf.group.views.group_about",
        default_tab="ietf.group.views.group_about",
        material_types=["slides"],
        default_used_roles=["auth", "chair"],
        admin_roles=["chair"],
        docman_roles=[],
        groupman_roles=[],
        matman_roles=[],
        role_order=["chair", "secr"],
        session_purposes=["officehours"],
    )
    Group.objects.filter(acronym__in=["rswg", "rsab"]).update(type_id="rfcedtyp")
    GroupTypeName.objects.create(
        slug="editorial",
        name="Editorial",
        desc="Editorial Stream Group",
        used=True,
    )
    GroupFeatures.objects.filter(type_id__in=["edwg", "edappr"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("group", "0059_use_timezone_now_for_group_models"),
        ("name", "0045_polls_and_chatlogs"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
