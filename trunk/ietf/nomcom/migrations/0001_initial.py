# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import ietf.nomcom.models
import ietf.nomcom.fields
import django.core.files.storage
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dbtemplate', '0001_initial'),
        ('name', '0001_initial'),
        ('person', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('author', models.EmailField(max_length=75, verbose_name=b'Author', blank=True)),
                ('subject', models.TextField(verbose_name=b'Subject', blank=True)),
                ('comments', ietf.nomcom.fields.EncryptedTextField(verbose_name=b'Comments')),
                ('time', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['time'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='NomCom',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('public_key', models.FileField(storage=django.core.files.storage.FileSystemStorage(location=b'/var/www/nomcom/public_keys/'), null=True, upload_to=ietf.nomcom.models.upload_path_handler, blank=True)),
                ('send_questionnaire', models.BooleanField(default=False, help_text=b'If you check this box, questionnaires are sent automatically after nominations', verbose_name=b'Send questionnaires automatically"')),
                ('reminder_interval', models.PositiveIntegerField(help_text=b'If the nomcom user sets the interval field then a cron command will                                                                send reminders to the nominees who have not responded using                                                                the following formula: (today - nomination_date) % interval == 0', null=True, blank=True)),
                ('initial_text', models.TextField(verbose_name=b'Help text for nomination form', blank=True)),
                ('group', models.ForeignKey(to='group.Group')),
            ],
            options={
                'verbose_name': 'NomCom',
                'verbose_name_plural': 'NomComs',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Nomination',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('candidate_name', models.CharField(max_length=255, verbose_name=b'Candidate name')),
                ('candidate_email', models.EmailField(max_length=255, verbose_name=b'Candidate email')),
                ('candidate_phone', models.CharField(max_length=255, verbose_name=b'Candidate phone', blank=True)),
                ('nominator_email', models.EmailField(max_length=75, verbose_name=b'Nominator Email', blank=True)),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('comments', models.ForeignKey(to='nomcom.Feedback')),
            ],
            options={
                'verbose_name_plural': 'Nominations',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Nominee',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('duplicated', models.ForeignKey(blank=True, to='nomcom.Nominee', null=True)),
                ('email', models.ForeignKey(to='person.Email')),
                ('nomcom', models.ForeignKey(to='nomcom.NomCom')),
            ],
            options={
                'verbose_name_plural': 'Nominees',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='NomineePosition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('nominee', models.ForeignKey(to='nomcom.Nominee')),
            ],
            options={
                'ordering': ['nominee'],
                'verbose_name': 'Nominee position',
                'verbose_name_plural': 'Nominee positions',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Position',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, verbose_name=b'Name')),
                ('description', models.TextField(verbose_name=b'Description')),
                ('is_open', models.BooleanField(default=False, verbose_name=b'Is open')),
                ('incumbent', models.ForeignKey(blank=True, to='person.Email', null=True)),
                ('nomcom', models.ForeignKey(to='nomcom.NomCom')),
                ('questionnaire', models.ForeignKey(related_name='questionnaire', editable=False, to='dbtemplate.DBTemplate', null=True)),
                ('requirement', models.ForeignKey(related_name='requirement', editable=False, to='dbtemplate.DBTemplate', null=True)),
            ],
            options={
                'verbose_name_plural': 'Positions',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ReminderDates',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date', models.DateField()),
                ('nomcom', models.ForeignKey(to='nomcom.NomCom')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='nomineeposition',
            name='position',
            field=models.ForeignKey(to='nomcom.Position'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='nomineeposition',
            name='state',
            field=models.ForeignKey(to='name.NomineePositionStateName'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='nomineeposition',
            unique_together=set([('position', 'nominee')]),
        ),
        migrations.AddField(
            model_name='nominee',
            name='nominee_position',
            field=models.ManyToManyField(to='nomcom.Position', through='nomcom.NomineePosition'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='nominee',
            unique_together=set([('email', 'nomcom')]),
        ),
        migrations.AddField(
            model_name='nomination',
            name='nominee',
            field=models.ForeignKey(to='nomcom.Nominee'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='nomination',
            name='position',
            field=models.ForeignKey(to='nomcom.Position'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='nomination',
            name='user',
            field=models.ForeignKey(editable=False, to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedback',
            name='nomcom',
            field=models.ForeignKey(to='nomcom.NomCom'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedback',
            name='nominees',
            field=models.ManyToManyField(to='nomcom.Nominee', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedback',
            name='positions',
            field=models.ManyToManyField(to='nomcom.Position', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedback',
            name='type',
            field=models.ForeignKey(blank=True, to='name.FeedbackTypeName', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedback',
            name='user',
            field=models.ForeignKey(blank=True, editable=False, to=settings.AUTH_USER_MODEL, null=True),
            preserve_default=True,
        ),
    ]
