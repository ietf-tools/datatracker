# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def forward(apps, schema_editor):
    SlideSubmission = apps.get_model("meeting", "SlideSubmission")
    Session = apps.get_model("meeting", "Session")
    SchedulingEvent = apps.get_model("meeting", "SchedulingEvent")
    Through = SlideSubmission.sessions.through

    latest_status = Subquery(
        SchedulingEvent.objects.filter(session=OuterRef("pk")).order_by("-time", "-id").values("status_id")[:1]
    )
    rows = []
    for submission in SlideSubmission.objects.select_related("session").iterator():
        session_ids = {submission.session_id}
        if submission.status_id == "pending" and submission.apply_to_all:
            # what approving with "apply to all" would have covered
            scheduled = (
                Session.objects.filter(
                    meeting_id=submission.session.meeting_id,
                    group_id=submission.session.group_id,
                    type_id__in=["regular", "plenary", "other"],
                )
                .annotate(current_status=latest_status)
                .filter(current_status="sched")
            )
            session_ids.update(scheduled.values_list("pk", flat=True))
        rows.extend(Through(slidesubmission_id=submission.pk, session_id=sid) for sid in session_ids)
    Through.objects.bulk_create(rows, batch_size=1000)


def reverse(apps, schema_editor):
    pass  # removing the field drops the through table, rows and all


class Migration(migrations.Migration):

    dependencies = [
        ("meeting", "0016_alter_meeting_country_alter_meeting_time_zone"),
    ]

    operations = [
        migrations.AddField(
            model_name="slidesubmission",
            name="sessions",
            field=models.ManyToManyField(
                blank=True,
                help_text="Sessions the deck is proposed for",
                related_name="proposed_slides",
                to="meeting.session",
            ),
        ),
        migrations.RunPython(forward, reverse),
    ]
