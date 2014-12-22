# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CommunityList',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('secret', models.CharField(max_length=255, null=True, blank=True)),
                ('cached', models.TextField(null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DisplayConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sort_method', models.CharField(default=b'by_filename', max_length=100, choices=[(b'by_filename', b'Alphabetical by I-D filename and RFC number'), (b'by_title', b'Alphabetical by document title'), (b'by_wg', b'Alphabetical by associated WG'), (b'date_publication', b'Date of publication of current version of the document'), (b'recent_change', b'Date of most recent change of status of any type'), (b'recent_significant', b'Date of most recent significant change of status')])),
                ('display_fields', models.TextField(default=b'filename,title,date')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DocumentChangeDates',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('new_version_date', models.DateTimeField(null=True, blank=True)),
                ('normal_change_date', models.DateTimeField(null=True, blank=True)),
                ('significant_change_date', models.DateTimeField(null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='EmailSubscription',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.CharField(max_length=200)),
                ('significant', models.BooleanField(default=False)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ExpectedChange',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('expected_date', models.DateField(verbose_name=b'Expected date')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ListNotification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('significant', models.BooleanField(default=False)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Rule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('rule_type', models.CharField(max_length=30, choices=[(b'wg_asociated', b'All I-Ds associated with a particular WG'), (b'area_asociated', b'All I-Ds associated with all WGs in a particular Area'), (b'ad_responsible', b'All I-Ds with a particular responsible AD'), (b'author', b'All I-Ds with a particular author'), (b'shepherd', b'All I-Ds with a particular document shepherd'), (b'with_text', b'All I-Ds that contain a particular text string in the name'), (b'in_iab_state', b'All I-Ds that are in a particular IAB state'), (b'in_iana_state', b'All I-Ds that are in a particular IANA state'), (b'in_iesg_state', b'All I-Ds that are in a particular IESG state'), (b'in_irtf_state', b'All I-Ds that are in a particular IRTF state'), (b'in_ise_state', b'All I-Ds that are in a particular ISE state'), (b'in_rfcEdit_state', b'All I-Ds that are in a particular RFC Editor state'), (b'in_wg_state', b'All I-Ds that are in a particular Working Group state'), (b'wg_asociated_rfc', b'All RFCs associated with a particular WG'), (b'area_asociated_rfc', b'All RFCs associated with all WGs in a particular Area'), (b'author_rfc', b'All RFCs with a particular author')])),
                ('value', models.CharField(max_length=255)),
                ('last_updated', models.DateTimeField(auto_now=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
