# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    GroupFeatures = apps.get_model("group", "GroupFeatures")
    GroupTypeName = apps.get_model("name", "GroupTypeName")

    iabworkshop = GroupFeatures.objects.create(
        type_id="iabworkshop",
        need_parent=True,
        default_parent="iab",
        has_documents=True,
        has_session_materials=True,
        has_meetings=True,
        has_default_chat=True,
        session_purposes='["regular"]',  
    )
    iabworkshop.parent_types.add(GroupTypeName.objects.get(slug="ietf"))


def reverse(apps, schema_editor):
    GroupFeatures = apps.get_model("group", "GroupFeatures")
    GroupFeatures.objects.filter(type="iabworkshop").delete()

class Migration(migrations.Migration):
    dependencies = [
        ("group", "0002_appeal"),
        ("name", "0009_iabworkshops"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
