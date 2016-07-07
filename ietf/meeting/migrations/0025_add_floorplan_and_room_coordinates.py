# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import ietf.utils.storage
import ietf.meeting.models


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0024_migrate_interim_meetings'),
    ]

    operations = [
        migrations.CreateModel(
            name='FloorPlan',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('order', models.SmallIntegerField()),
                ('image', models.ImageField(default=None, storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=ietf.meeting.models.floorplan_path, blank=True)),
                ('meeting', models.ForeignKey(to='meeting.Meeting')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='room',
            name='floorplan',
            field=models.ForeignKey(default=None, blank=True, to='meeting.FloorPlan', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='room',
            name='x1',
            field=models.SmallIntegerField(default=None, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='room',
            name='x2',
            field=models.SmallIntegerField(default=None, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='room',
            name='y1',
            field=models.SmallIntegerField(default=None, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='room',
            name='y2',
            field=models.SmallIntegerField(default=None, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterModelOptions(
            name='room',
            options={'ordering': ['-meeting', 'name']},
        ),
    ]
