# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from tqdm import tqdm
from django.db import migrations
from ietf.submit.checkers import DraftIdnitsChecker, DraftYangChecker

def set_submission_check_symbol(apps, schema_editor):
    SubmissionCheck = apps.get_model('submit','SubmissionCheck')
    checks = SubmissionCheck.objects.all()
    print("")
    print("    Adding submission check symbol info to existing checks")
    for s in tqdm(checks):
        if not s.symbol:
            if s.checker == "idnits check":
                s.symbol = DraftIdnitsChecker.symbol
            if s.checker == 'yang validation':
                s.symbol = DraftYangChecker.symbol
            s.save()

def backward(apps, schema_editor):
    SubmissionCheck = apps.get_model('submit','SubmissionCheck')
    for s in SubmissionCheck.objects.all():
        if s.symbol != "":
            s.symbol = ""
            s.save()

class Migration(migrations.Migration):

    dependencies = [
        ('submit', '0009_submissioncheck_symbol'),
    ]

    operations = [
        migrations.RunPython(set_submission_check_symbol, backward)
    ]
