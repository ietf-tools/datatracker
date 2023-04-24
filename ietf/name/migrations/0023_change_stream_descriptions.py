# Copyright The IETF Trust 2019-2021, All Rights Reserved
# -*- coding: utf-8 -*-

from django.db import migrations


def forward(apps, schema_editor):
    # Change the StreamName descriptions to match what appears in modern RFCs
    StreamName = apps.get_model('name', 'StreamName')
    for streamName in StreamName.objects.all():
        if streamName.name == "IETF":
            streamName.desc = "Internent Engineering Task Force (IETF)"
        elif streamName.name == "IRTF":
            streamName.desc = "Internet Research Task Force (IRTF)"
        elif streamName.name == "IAB":
            streamName.desc = "Internet Architecture Board (IAB)"
        elif streamName.name == "ISE":
            streamName.desc = "Independent Submission"
        streamName.save()


def reverse(apps, schema_editor):
    StreamName = apps.get_model('name', 'StreamName')
    for streamName in StreamName.objects.all():
        if streamName.name == "IETF":
            streamName.desc = "IETF stream"
        elif streamName.name == "IRTF":
            streamName.desc = "IRTF Stream"
        elif streamName.name == "IAB":
            streamName.desc = "IAB stream"
        elif streamName.name == "ISE":
            streamName.desc = "Independent Submission Editor stream"
        streamName.save()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0022_add_liaison_contact_rolenames'),
    ]

    operations = [
        migrations.RunPython(forward,reverse),

    ]

