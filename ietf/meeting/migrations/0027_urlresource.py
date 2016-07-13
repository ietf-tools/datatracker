# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0013_add_group_type_verbose_name_data'),
        ('meeting', '0026_add_floorplan_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='UrlResource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('url', models.URLField(null=True, blank=True)),
                ('name', models.ForeignKey(to='name.RoomResourceName')),
                ('room', models.ForeignKey(to='meeting.Room')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
