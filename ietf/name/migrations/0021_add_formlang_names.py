# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def insert_initial_formal_language_names(apps, schema_editor):
    FormalLanguageName = apps.get_model("name", "FormalLanguageName")
    FormalLanguageName.objects.get_or_create(slug="abnf", name="ABNF", desc="Augmented Backus-Naur Form", order=1)
    FormalLanguageName.objects.get_or_create(slug="asn1", name="ASN.1", desc="Abstract Syntax Notation One", order=2)
    FormalLanguageName.objects.get_or_create(slug="cbor", name="CBOR", desc="Concise Binary Object Representation", order=3)
    FormalLanguageName.objects.get_or_create(slug="ccode", name="C Code", desc="Code in the C Programming Language", order=4)
    FormalLanguageName.objects.get_or_create(slug="json", name="JSON", desc="Javascript Object Notation", order=5)
    FormalLanguageName.objects.get_or_create(slug="xml", name="XML", desc="Extensible Markup Language", order=6)

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0020_formallanguagename'),
    ]

    operations = [
        migrations.RunPython(insert_initial_formal_language_names, migrations.RunPython.noop)
    ]
