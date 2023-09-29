# Copyright The IETF Trust 2023, All Rights Reserved

import debug # pyflakes: ignore

from django.db import migrations
from django.db.models import Subquery, OuterRef, F

def forward(apps, schema_editor):
    """Move RFC events from the draft to the rfc Document"""
    import datetime; start=datetime.datetime.now()
    DocEvent = apps.get_model("doc", "DocEvent")
    Document = apps.get_model("doc", "Document")
    RelatedDocument = apps.get_model("doc", "RelatedDocument")

    # queryset with events migrated regardless of whether before or after the "published_rfc" event
    events_always_migrated = DocEvent.objects.filter(doc__type_id="draft", type="published_rfc")

    # queryset with events migrated only after the "published_rfc" event
    events_migrated_after_pub = DocEvent.objects.filter(doc__type_id="draft").exclude(
        type__in=[
            "created_ballot",
            "closed_ballot",
            "sent_ballot_announcement",
            "changed_ballot_position",
            "changed_ballot_approval_text",
            "changed_ballot_writeup_text",
        ]
    ).exclude(
        type="added_comment",
        desc__contains="ballot set",  # excludes 311 comments that all apply to drafts
    )

    # special case for rfc 6312/6342 draft, which has two published_rfc events
    rfc6312 = Document.objects.get(name="rfc6312")
    rfc6342 = Document.objects.get(name="rfc6342")
    draft = RelatedDocument.objects.get(relationship_id="became_rfc",target=rfc6312).source
    assert draft == RelatedDocument.objects.get(relationship_id="became_rfc",target=rfc6342).source
    published_events = list(
        DocEvent.objects.filter(doc=draft, type="published_rfc").order_by("time")
    )
    assert len(published_events) == 2
    (
        pub_event_6312,
        pub_event_6342,
    ) = published_events  # order matches pub dates at rfc-editor.org

    pub_event_6312.doc = rfc6312
    pub_event_6312.save()
    events_migrated_after_pub.filter(
        doc=draft,
        time__gte=pub_event_6312.time,
        time__lt=pub_event_6342.time,
    ).update(doc=rfc6312)

    pub_event_6342.doc = rfc6342
    pub_event_6342.save()
    events_migrated_after_pub.filter(
        doc=draft,
        time__gte=pub_event_6342.time,
    ).update(doc=rfc6342)


    events_migrated_after_pub.exclude(doc=draft).annotate(
        rfcdoc_id = Subquery(RelatedDocument.objects.filter(relationship_id="became_rfc",source_id=OuterRef("doc_id")).values_list("target_id",flat=True)[:1])
    ).annotate(
        rfcpubdate = Subquery(DocEvent.objects.filter(doc_id=OuterRef("doc_id"),type="published_rfc").values_list("time")[:1])
    ).filter(time__gte=F("rfcpubdate")).update(doc_id=F("rfcdoc_id"))

    events_always_migrated.exclude(doc=draft).annotate(
        rfcdoc_id = Subquery(RelatedDocument.objects.filter(relationship_id="became_rfc",source_id=OuterRef("doc_id")).values_list("target_id",flat=True)[:1])
    ).update(doc_id=F("rfcdoc_id"))

    end = datetime.datetime.now()
    debug.show("end-start")

class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0019_move_errata_tags"),
    ]

    operations = [
        migrations.RunPython(forward)
    ]
