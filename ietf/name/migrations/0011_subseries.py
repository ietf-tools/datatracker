# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    DocTypeName = apps.get_model("name", "DocTypeName")
    DocRelationshipName = apps.get_model("name", "DocRelationshipName")
    for slug, name, prefix in [
        ("std", "Standard", "std"),
        ("bcp", "Best Current Practice", "bcp"),
        ("fyi", "For Your Information", "fyi"),
    ]:
        DocTypeName.objects.create(
            slug=slug, name=name, prefix=prefix, desc="", used=True
        )
    DocRelationshipName.objects.create(
        slug="contains",
        name="Contains",
        revname="Is part of",
        desc="This document contains other documents (e.g., STDs contain RFCs)",
        used=True,
    )


def reverse(apps, schema_editor):
    DocTypeName = apps.get_model("name", "DocTypeName")
    DocRelationshipName = apps.get_model("name", "DocRelationshipName")
    DocTypeName.objects.filter(slug__in=["std", "bcp", "fyi"]).delete()
    DocRelationshipName.objects.filter(slug="contains").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("name", "0010_rfc_doctype_names"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
