# Copyright The IETF Trust 2025 All Rights Reserved
from django.db import migrations, models
import ietf.utils.validators


class Migration(migrations.Migration):
    dependencies = [
        ("liaisons", "0002_alter_liaisonstatement_response_contacts"),
    ]

    operations = [
        migrations.AddField(
            model_name="liaisonstatement",
            name="from_contact_tmp",
            field=models.CharField(
                blank=True,
                help_text="Address of the formal sender of the statement",
                max_length=512,
                validators=[ietf.utils.validators.validate_mailbox_address],
            ),
        ),
    ]
