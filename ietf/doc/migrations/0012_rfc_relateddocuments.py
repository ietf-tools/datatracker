# Generated by Django 4.2.3 on 2023-07-05 22:40

from django.db import migrations


def forward(apps, schema_editor):
    DocAlias = apps.get_model("doc", "DocAlias")
    Document = apps.get_model("doc", "Document")
    RelatedDocument = apps.get_model("doc", "RelatedDocument")
    for rfc_alias in DocAlias.objects.filter(name__startswith="rfc").exclude(
        docs__type_id="rfc"
    ):
        # Move these over to the RFC
        RelatedDocument.objects.filter(
            relationship__slug__in=(
                "tobcp",
                "toexp",
                "tohist",
                "toinf",
                "tois",
                "tops",
                "obs",
                "updates",
            ),
            source__docalias=rfc_alias,
        ).update(source=Document.objects.get(name=rfc_alias.name))
        # Duplicate references on the RFC but keep the ones on the draft as well
        originals = list(
            RelatedDocument.objects.filter(
                relationship__slug__in=("refinfo", "refnorm", "refold", "refunk"),
                source__docalias=rfc_alias,
            )
        )
        for o in originals:
            o.pk = None
            o.source = Document.objects.get(name=rfc_alias.name)
        RelatedDocument.objects.bulk_create(originals)


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0011_move_rfc_docevents"),
    ]

    operations = [migrations.RunPython(forward)]