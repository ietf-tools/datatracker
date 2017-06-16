# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from tqdm import tqdm
from django.db import migrations

def populate_submission_draft(apps, schema_editor):
    Submission = apps.get_model('submit', 'Submission')
    Document = apps.get_model('doc', 'Document')
    print("")
    submissions = Submission.objects.filter(state_id='posted', draft=None)
    count = submissions.count()
    print("    Fixing up draft information for %s submissions" % count)
    for submission in tqdm(submissions):
        try:
            draft = Document.objects.get(name=submission.name)
        except Document.DoesNotExist:
            print( "    Failed to find %s-%s" % (submission.name, submission.rev))
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
