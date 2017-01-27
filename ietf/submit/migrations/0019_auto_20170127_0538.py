# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
import jsonfield.fields

def parse_email_line(line):
    """Split line on the form 'Some Name <email@example.com>'"""
    import re
    m = re.match("([^<]+) <([^>]+)>$", line)
    if m:
        return dict(name=m.group(1), email=m.group(2))
    else:
        return dict(name=line, email="")

def parse_authors(author_lines):
    res = []
    for line in author_lines.replace("\r", "").split("\n"):
        line = line.strip()
        if line:
            res.append(parse_email_line(line))
    return res

def convert_author_lines_to_json(apps, schema_editor):
    import json

    Submission = apps.get_model("submit", "Submission")
    for s in Submission.objects.all().iterator():
        Submission.objects.filter(pk=s.pk).update(authors=json.dumps(parse_authors(s.authors)))

class Migration(migrations.Migration):

    dependencies = [
        ('submit', '0018_auto_20170116_0927'),
    ]

    operations = [
        migrations.RunPython(convert_author_lines_to_json, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='submission',
            name='authors',
            field=jsonfield.fields.JSONField(default=list, help_text=b'List of authors with name, email, affiliation and country code.'),
        ),
    ]
