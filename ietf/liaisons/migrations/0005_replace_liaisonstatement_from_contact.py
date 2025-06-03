# Copyright The IETF Trust 2025 All Rights Reserved
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("liaisons", "0004_populate_liaisonstatement_from_contact_tmp"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="liaisonstatement",
            name="from_contact",
        ),
        migrations.RenameField(
            model_name="liaisonstatement",
            old_name="from_contact_tmp",
            new_name="from_contact",
        ),
    ]
