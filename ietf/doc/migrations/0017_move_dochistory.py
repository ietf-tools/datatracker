# Copyright The IETF Trust 2023, All Rights Reserved

import debug # pyflakes: ignore
from django.db import migrations

from django.db.models import Subquery, OuterRef, F


def forward(apps, schema_editor):
    import datetime; start=datetime.datetime.now()
    DocHistory = apps.get_model("doc", "DocHistory")
    RelatedDocument = apps.get_model("doc", "RelatedDocument")
    Document = apps.get_model("doc", "Document")
    DocHistory.objects.filter(type_id="draft", doc__type_id="rfc").update(type_id="rfc")
    DocHistory.objects.filter(
        type_id="draft", doc__type_id="draft", name__startswith="rfc"
    ).annotate(
        rfc_id=Subquery(
            RelatedDocument.objects.filter(
                source_id=OuterRef("doc_id"), relationship_id="became_rfc"
            ).values_list("target_id", flat=True)[:1]
        )
    ).update(
        doc_id=F("rfc_id"), type_id="rfc"
    )
    DocHistory.objects.filter(type_id="rfc").annotate(
        rfcno=Subquery(
            Document.objects.filter(pk=OuterRef("doc_id")).values_list(
                "rfc_number", flat=True
            )[:1]
        )
    ).update(rfc_number=F("rfcno"))
    assert not DocHistory.objects.filter(
        name__startswith="rfc", type_id="draft"
    ).exists()
    assert not DocHistory.objects.filter(
        type_id="rfc", rfc_number__isnull=True
    ).exists()
    end=datetime.datetime.now(); debug.show("end-start")


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0016_delete_docalias"),
    ]

    # There is no going back
    operations = [migrations.RunPython(forward)]
