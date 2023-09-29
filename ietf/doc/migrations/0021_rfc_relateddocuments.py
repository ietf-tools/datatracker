# Copyright The IETF Trust 2023, All Rights Reserved

import debug # pyflakes:ignore

from django.db import migrations
from django.db.models import Subquery, OuterRef, F

def forward(apps, schema_editor):
    import datetime; start = datetime.datetime.now()
    Document = apps.get_model("doc", "Document")
    RelatedDocument = apps.get_model("doc", "RelatedDocument")

    # Move these over to the RFC
    RelatedDocument.objects.filter(
        source__type_id="draft",
        relationship__slug__in=(
            "tobcp",
            "toexp",
            "tohist",
            "toinf",
            "tois",
            "tops",
            "obs",
            "updates",
        )
    ).annotate(
        rfcdoc_id = Subquery(RelatedDocument.objects.filter(source_id=OuterRef("source_id"),relationship_id="became_rfc").values_list("target_id",flat=True)[:1])
    ).update(source_id=F("rfcdoc_id"))


    # Duplicate references on the RFC but keep the ones on the draft as well
    originals = list(
        RelatedDocument.objects.filter(
            source__type_id="draft",
            relationship__slug__in=("refinfo", "refnorm", "refold", "refunk"),
        ).annotate(
            rfcdoc_id = Subquery(RelatedDocument.objects.filter(source_id=OuterRef("source_id"),relationship_id="became_rfc").values_list("target_id",flat=True)[:1])
        ).filter(rfcdoc_id__isnull=False)
    )
    for o in originals:
        o.pk = None
        o.source_id = o.rfcdoc_id
    RelatedDocument.objects.bulk_create(originals)

    end = datetime.datetime.now()
    debug.show("end-start")

class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0020_move_rfc_docevents"),
    ]

    operations = [
        migrations.RunPython(forward)
    ]
