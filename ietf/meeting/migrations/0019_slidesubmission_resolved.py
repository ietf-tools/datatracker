# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion
import ietf.utils.models


def forward(apps, schema_editor):
    """Approved proposals get who approved them and when, from the document's approval event"""
    SlideSubmission = apps.get_model("meeting", "SlideSubmission")
    DocEvent = apps.get_model("doc", "DocEvent")
    approvals = {}
    for event in DocEvent.objects.filter(type="approved_slides").order_by("time", "id").values("doc_id", "time", "by_id"):
        approvals.setdefault(event["doc_id"], []).append(event)
    for submission in SlideSubmission.objects.filter(status_id="approved", doc__isnull=False).iterator():
        events = approvals.get(submission.doc_id)
        if not events:
            continue
        # approving saved the row after creating the event, so the proposal's time (auto_now) sits
        # just after its own event: take the event nearest in time, not the first one after
        event = min(events, key=lambda e: abs(e["time"] - submission.time))
        SlideSubmission.objects.filter(pk=submission.pk).update(resolved=event["time"], resolved_by_id=event["by_id"])


def reverse(apps, schema_editor):
    pass  # the fields go with the reversal


class Migration(migrations.Migration):

    dependencies = [
        ("doc", "0038_rpcactionholderopenentry"),
        ("person", "0006_personuuid"),
        ("meeting", "0018_remove_slidesubmission_apply_to_all"),
    ]

    operations = [
        migrations.AddField(
            model_name="slidesubmission",
            name="resolved",
            field=models.DateTimeField(
                blank=True,
                help_text="When the proposal stopped being pending",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="slidesubmission",
            name="resolved_by",
            field=ietf.utils.models.ForeignKey(
                blank=True,
                help_text="Who approved, declined or withdrew it; (System) when it expired",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="resolved_slide_proposals",
                to="person.person",
            ),
        ),
        migrations.RunPython(forward, reverse),
    ]
