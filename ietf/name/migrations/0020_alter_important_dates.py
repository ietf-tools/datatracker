# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations

def reverse_markdown(apps, schema_editor):
    ImportantDateName = apps.get_model("name", "ImportantDateName")
    slugs = ["bofproposals", "openreg", "opensched", "cutoffwgreq", "idcutoff", "cutoffwgreq", "bofprelimcutoff", "cutoffbofreq"]
    ImportantDateName.objects.filter(pk__in=slugs).update(desc="")

class Migration(migrations.Migration):
    dependencies = [
        ("name", "0019_alter_sessionpurposename_timeslot_types"),
    ]

    operations = [
        migrations.RunPython(reverse_markdown),
    ]
