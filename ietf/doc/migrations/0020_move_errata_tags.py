# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

from django.db.models import Subquery, OuterRef, F


def forward(apps, schema_editor):
    Document = apps.get_model("doc", "Document")
    RelatedDocument = apps.get_model("doc", "RelatedDocument")
    Document.tags.through.objects.filter(
        doctagname_id__in=["errata", "verified-errata"], document__type_id="draft"
    ).annotate(
        rfcdoc=Subquery(
            RelatedDocument.objects.filter(
                relationship_id="became_rfc", source_id=OuterRef("document__pk")
            ).values_list("target__pk", flat=True)[:1]
        )
    ).update(
        document_id=F("rfcdoc")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0019_subseries"),
    ]

    operations = [migrations.RunPython(forward)]
