# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def populate_submission_draft(apps, schema_editor):
    Submission = apps.get_model('submit', 'Submission')
    Document = apps.get_model('doc', 'Document')
    print("")
    for submission in Submission.objects.filter(state_id='posted'):
        if submission.draft == None:
            try:
                draft = Document.objects.get(name=submission.name)
            except Document.DoesNotExist:
                print( "Failed to find %s-%s" % (submission.name, submission.rev))
                continue
            submission.draft = draft
            submission.save()

def backward(apps, schema_editor):
    pass                                # nothing to do

class Migration(migrations.Migration):

    dependencies = [
        ('submit', '0007_submission_draft'),
    ]

    operations = [
        migrations.RunPython(populate_submission_draft, backward)
    ]
