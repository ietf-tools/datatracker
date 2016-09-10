# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import date

from django.db import migrations
from ietf.submit.utils import remove_submission_files


class Migration(migrations.Migration):
    def remove_old_submissions(apps, schema_editor):
        """
        We'll remove any submissions awaiting manual post that are older
        than a date provided here.
        
        These all showed up when we added the ability to list submissions
        awaiting manual post and go back many years
        """

        # We can't import the model directly as it may be a newer
        # version than this migration expects. We use the historical version.
        before=date(2016, 3, 1)
        Submission = apps.get_model("submit", "Submission")
        DraftSubmissionStateName = apps.get_model("name", "DraftSubmissionStateName")

        cancelled = DraftSubmissionStateName.objects.get(slug="cancel")     
        for submission in Submission.objects.filter(state_id = "manual", submission_date__lt=before).distinct():
            submission.state = cancelled
            submission.save()
        
            remove_submission_files(submission)

    def reverse(apps, schema_editor):
        pass

    dependencies = [
        ('submit', '0012_auto_20160414_1902'),
    ]

    operations = [
        migrations.RunPython(remove_old_submissions, reverse),
    ]
