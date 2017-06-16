# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations # pyflakes:ignore

def add_doc_type_prefix(apps, schema_editor):
    DocTypeName = apps.get_model("name", "DocTypeName")
    prefixes = {
        u'agenda':      u'agenda',
        u'bluesheets':  u'bluesheets',
        u'charter':     u'charter',
        u'conflrev':    u'conflict-review',
        u'draft':       u'draft',
        u'liai-att':    u'liai-att',
        u'minutes':     u'minutes',
        u'recording':   u'recording',
        u'slides':      u'slides',
        u'statchg':     u'status-change',
    }

    for slug, prefix in prefixes.items():
        o = DocTypeName.objects.get(slug=slug)
        o.prefix = prefix
        o.save()

def del_doc_type_prefix(apps, schema_editor):
    DocTypeName = apps.get_model("name", "DocTypeName")
    for o in DocTypeName.objects.all():
        o.prefix = ""
        o.save()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0008_doctypename_prefix'),
    ]

    operations = [
        migrations.RunPython(add_doc_type_prefix, del_doc_type_prefix),

    ]
