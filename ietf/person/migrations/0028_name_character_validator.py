# Copyright The IETF Trust 2022, All Rights Reserved

from django.db import migrations, models
import ietf.person.models


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0027_personevent_drop_consent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalperson',
            name='name',
            field=models.CharField(db_index=True, help_text='Preferred long form of name.', max_length=255, validators=[ietf.person.models.name_character_validator], verbose_name='Full Name (Unicode)'),
        ),
        migrations.AlterField(
            model_name='person',
            name='name',
            field=models.CharField(db_index=True, help_text='Preferred long form of name.', max_length=255, validators=[ietf.person.models.name_character_validator], verbose_name='Full Name (Unicode)'),
        ),
    ]
