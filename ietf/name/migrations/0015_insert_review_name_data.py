# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def insert_initial_review_data(apps, schema_editor):
    ReviewRequestStateName = apps.get_model("name", "ReviewRequestStateName")
    ReviewRequestStateName.objects.get_or_create(slug="requested", name="Requested", order=1)
    ReviewRequestStateName.objects.get_or_create(slug="accepted", name="Accepted", order=2)
    ReviewRequestStateName.objects.get_or_create(slug="rejected", name="Rejected", order=3)
    ReviewRequestStateName.objects.get_or_create(slug="withdrawn", name="Withdrawn", order=4)
    ReviewRequestStateName.objects.get_or_create(slug="overtaken", name="Overtaken by Events", order=5)
    ReviewRequestStateName.objects.get_or_create(slug="no-response", name="No Response", order=6)
    ReviewRequestStateName.objects.get_or_create(slug="no-review-version", name="Team Will not Review Version", order=7)
    ReviewRequestStateName.objects.get_or_create(slug="no-review-document", name="Team Will not Review Document", order=8)
    ReviewRequestStateName.objects.get_or_create(slug="part-completed", name="Partially Completed", order=9)
    ReviewRequestStateName.objects.get_or_create(slug="completed", name="Completed", order=10)

    ReviewTypeName = apps.get_model("name", "ReviewTypeName")
    ReviewTypeName.objects.get_or_create(slug="early", name="Early", order=1)
    ReviewTypeName.objects.get_or_create(slug="lc", name="Last Call", order=2)
    ReviewTypeName.objects.get_or_create(slug="telechat", name="Telechat", order=3)

    ReviewResultName = apps.get_model("name", "ReviewResultName")
    ReviewResultName.objects.get_or_create(slug="serious-issues", name="Serious Issues", order=1)
    ReviewResultName.objects.get_or_create(slug="issues", name="Has Issues", order=2)
    ReviewResultName.objects.get_or_create(slug="nits", name="Has Nits", order=3)

    ReviewResultName.objects.get_or_create(slug="not-ready", name="Not Ready", order=4)
    ReviewResultName.objects.get_or_create(slug="right-track", name="On the Right Track", order=5)
    ReviewResultName.objects.get_or_create(slug="almost-ready", name="Almost Ready", order=6)

    ReviewResultName.objects.get_or_create(slug="ready-issues", name="Ready with Issues", order=7)
    ReviewResultName.objects.get_or_create(slug="ready-nits", name="Ready with Nits", order=8)
    ReviewResultName.objects.get_or_create(slug="ready", name="Ready", order=9)

    RoleName = apps.get_model("name", "RoleName")
    RoleName.objects.get_or_create(slug="reviewer", name="Reviewer", order=max(r.order for r in RoleName.objects.exclude(slug="reviewer")) + 1)

    DocTypeName = apps.get_model("name", "DocTypeName")
    DocTypeName.objects.get_or_create(slug="review", name="Review")

    StateType = apps.get_model("doc", "StateType")
    review_state_type, _ = StateType.objects.get_or_create(slug="review", label="Review")

    State = apps.get_model("doc", "State")
    State.objects.get_or_create(type=review_state_type, slug="active", name="Active", order=1)
    State.objects.get_or_create(type=review_state_type, slug="deleted", name="Deleted", order=2)

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0014_reviewrequeststatename_reviewresultname_reviewtypename'),
        ('group', '0001_initial'),
        ('doc', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(insert_initial_review_data, noop),
    ]
