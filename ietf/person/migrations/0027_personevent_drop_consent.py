# Copyright The IETF Trust 2022, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0026_drop_consent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='personevent',
            name='type',
            field=models.CharField(choices=[('apikey_login', 'API key login'), ('email_address_deactivated', 'Email address deactivated')], max_length=50),
        ),
    ]
