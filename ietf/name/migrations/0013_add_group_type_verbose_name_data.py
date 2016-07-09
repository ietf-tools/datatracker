# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

verbose_names = {
    "wg":       "Working Group",
    "team":	"Team",
    "sdo":      "Standards Organization",
    "rg":       "Research Group",
    "rfcedtyp":	"The RFC Editor",
    "nomcom":	"IETF/IAB Nominating Committee",
    "isoc":	"The Internet Society",
    "irtf":	"Internet Research Task Force",
    "individ":	"An Individual",
    "ietf":	"Internet Engineering Task Force",
    "iab":      "Internet Architecture Board",
    "dir":      "Area Directorate",
    "area":	"Area",
    "ag":       "Area Group",
}

def forward(apps, schema_editor):
    GroupTypeName  = apps.get_model('name', 'GroupTypeName')
    for slug, verbose_name in verbose_names.items():
        name = GroupTypeName.objects.get(slug=slug)
        name.verbose_name = verbose_name
        name.save()

def backward(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0012_grouptypename_verbose_name'),
    ]

    operations = [
        migrations.RunPython(forward, backward)
    ]
