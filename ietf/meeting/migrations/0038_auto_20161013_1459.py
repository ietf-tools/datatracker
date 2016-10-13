# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from ietf.meeting.utils import create_proceedings_templates

def create_attendee_templates(apps, schema_editor):
    """Create attendee templates for supported meetings"""
    Meeting = apps.get_model("meeting", "Meeting")
    create_proceedings_templates(Meeting.objects.get(number=95))
    create_proceedings_templates(Meeting.objects.get(number=96))

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0037_change_meta_options_on_sessionpresentation'),
    ]

    operations = [
        migrations.RunPython(create_attendee_templates),
    ]
