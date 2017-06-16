# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

from django.db import migrations

def convert_to_submission_check(apps, schema_editor):
    Submission = apps.get_model('submit','Submission')
    SubmissionCheck = apps.get_model('submit','SubmissionCheck')
    for s in Submission.objects.all():
        passed = re.search('\s+Summary:\s+0\s+|No nits found', s.idnits_message) != None
        c = SubmissionCheck(submission=s, checker='idnits check', passed=passed, message=s.idnits_message)
        c.save()

def convert_from_submission_check(apps, schema_editor):
    SubmissionCheck = apps.get_model('submit','SubmissionCheck')
    for c in SubmissionCheck.objects.filter(checker='idnits check'):
        c.submission.idnits_message = c.message
        c.save()
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('submit', '0004_submissioncheck'),
    ]

    operations = [
        migrations.RunPython(convert_to_submission_check, convert_from_submission_check)
    ]
