# Copyright The IETF Trust 2023, All Rights Reserved

import debug  # pyflakes: ignore

from django.db import migrations
from django.db.models import Count, Min, Max, Subquery, OuterRef


def forward(apps, schema_editor):
    import datetime

    start = datetime.datetime.now()
    Document = apps.get_model("doc", "Document")
    DocAlias = apps.get_model("doc", "DocAlias")
    DocumentAuthor = apps.get_model("doc", "DocumentAuthor")

    State = apps.get_model("doc", "State")
    draft_rfc_state = State.objects.get(type_id="draft", slug="rfc")
    rfc_published_state = State.objects.get(type_id="rfc", slug="published")

    DocTypeName = apps.get_model("name", "DocTypeName")
    rfc_doctype = DocTypeName(slug="rfc")

    # Find draft Documents in the "rfc" state
    found_by_state = Document.objects.filter(states=draft_rfc_state).distinct()

    # Find Documents with an "rfc..." alias and confirm they're the same set
    rfc_docaliases = DocAlias.objects.filter(name__startswith="rfc").annotate(
        draft_id=Subquery(
            DocAlias.docs.through.objects.filter(
                docalias_id=OuterRef("pk")
            ).values_list("document_id", flat=True)[:1]
        )
    )
    found_by_name = Document.objects.filter(docalias__in=rfc_docaliases).distinct()
    assert set(found_by_name) == set(
        found_by_state
    ), "mismatch between rfcs identified by state and docalias"

    # As of 2023-06-15, there is one Document with two rfc aliases: rfc6312 and rfc6342 are the same Document. This
    # was due to a publication error. Because we go alias-by-alias, no special handling is needed in this migration.

    assert rfc_docaliases.annotate(Count("docs")).aggregate(
        Max("docs__count"), Min("docs__count")
    ) == {"docs__count__max": 1, "docs__count__min": 1}

    drafts = {
        d.pk: d
        for d in Document.objects.filter(
            pk__in=rfc_docaliases.values_list("draft_id", flat=True)
        ).prefetch_related("formal_languages")
    }

    top_loop = datetime.timedelta(0)
    bottom_loop = datetime.timedelta(0)
    author_loop = datetime.timedelta(0)
    for rfc_alias in rfc_docaliases.order_by("name"):
        draft = drafts[rfc_alias.draft_id]
        if draft.name.startswith("rfc"):
            s = datetime.datetime.now()
            rfc = draft
            rfc.type_id = "rfc"
            rfc.rfc_number = int(draft.name[3:])
            rfc.save()
            rfc.states.set([rfc_published_state])
            top_loop += datetime.datetime.now() - s
        else:
            s = datetime.datetime.now()
            rfc = Document.objects.create(
                type_id="rfc",
                name=rfc_alias.name,
                rfc_number=int(rfc_alias.name[3:]),
                time=draft.time,
                title=draft.title,
                stream_id=draft.stream_id,
                group_id=draft.group_id,
                abstract=draft.abstract,
                pages=draft.pages,
                words=draft.words,
                std_level_id=draft.std_level_id,
                ad_id=draft.ad_id,
                external_url=draft.external_url,
                uploaded_filename=draft.uploaded_filename,
                note=draft.note,
            )
            rfc.states.set([rfc_published_state])
            rfc.formal_languages.set(draft.formal_languages.all())
            bottom_loop += datetime.datetime.now() - s

            # Copy Authors
            s = datetime.datetime.now()
            for da in draft.documentauthor_set.all():
                DocumentAuthor.objects.create(
                    document=rfc,
                    person_id=da.person_id,
                    email_id=da.email_id,
                    affiliation=da.affiliation,
                    country=da.country,
                    order=da.order,
                )
            author_loop += datetime.datetime.now() - s
    end = datetime.datetime.now()
    debug.show("[top_loop,bottom_loop,author_loop]")
    debug.show("end-start")


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0009_dochistory_rfc_number_document_rfc_number"),
        ("name", "0009_rfc_doctype_names"),
    ]

    operations = [
        migrations.RunPython(forward),
    ]
