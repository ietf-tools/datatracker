# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def add_affiliation_info(apps, schema_editor):
    AffiliationAlias = apps.get_model("person", "AffiliationAlias")

    AffiliationAlias.objects.get_or_create(alias="cisco", name="Cisco Systems")
    AffiliationAlias.objects.get_or_create(alias="cisco system", name="Cisco Systems")
    AffiliationAlias.objects.get_or_create(alias="cisco systems (india) private limited", name="Cisco Systems")
    AffiliationAlias.objects.get_or_create(alias="cisco systems india pvt", name="Cisco Systems")

    AffiliationIgnoredEnding = apps.get_model("person", "AffiliationIgnoredEnding")
    AffiliationIgnoredEnding.objects.get_or_create(ending="LLC\.?")
    AffiliationIgnoredEnding.objects.get_or_create(ending="Ltd\.?")
    AffiliationIgnoredEnding.objects.get_or_create(ending="Inc\.?")
    AffiliationIgnoredEnding.objects.get_or_create(ending="GmbH\.?")


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0015_affiliationalias_affiliationignoredending'),
    ]

    operations = [
        migrations.RunPython(add_affiliation_info, migrations.RunPython.noop)
    ]
