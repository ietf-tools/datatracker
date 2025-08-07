# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(default=b'', max_length=100)),
                ('client_id', models.CharField(unique=True, max_length=255)),
                ('client_secret', models.CharField(unique=True, max_length=255)),
                ('response_type', models.CharField(max_length=30, choices=[
                    (b'code', b'code (Authorization Code Flow)'), (b'id_token', b'id_token (Implicit Flow)'),
                    (b'id_token token', b'id_token token (Implicit Flow)')])),
                ('_redirect_uris', models.TextField(default=b'')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Code',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('expires_at', models.DateTimeField()),
                ('_scope', models.TextField(default=b'')),
                ('code', models.CharField(unique=True, max_length=255)),
                ('client', models.ForeignKey(to='oidc_provider.Client', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Token',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('expires_at', models.DateTimeField()),
                ('_scope', models.TextField(default=b'')),
                ('access_token', models.CharField(unique=True, max_length=255)),
                ('_id_token', models.TextField()),
                ('client', models.ForeignKey(to='oidc_provider.Client', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserInfo',
            fields=[
                ('user', models.OneToOneField(primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
                ('given_name', models.CharField(max_length=255, null=True, blank=True)),
                ('family_name', models.CharField(max_length=255, null=True, blank=True)),
                ('middle_name', models.CharField(max_length=255, null=True, blank=True)),
                ('nickname', models.CharField(max_length=255, null=True, blank=True)),
                ('gender', models.CharField(max_length=100, null=True, choices=[(b'F', b'Female'), (b'M', b'Male')])),
                ('birthdate', models.DateField(null=True)),
                ('zoneinfo', models.CharField(default=b'', max_length=100, null=True, blank=True)),
                ('preferred_username', models.CharField(max_length=255, null=True, blank=True)),
                ('profile', models.URLField(default=b'', null=True, blank=True)),
                ('picture', models.URLField(default=b'', null=True, blank=True)),
                ('website', models.URLField(default=b'', null=True, blank=True)),
                ('email_verified', models.NullBooleanField(default=False)),
                ('locale', models.CharField(max_length=100, null=True, blank=True)),
                ('phone_number', models.CharField(max_length=255, null=True, blank=True)),
                ('phone_number_verified', models.NullBooleanField(default=False)),
                ('address_street_address', models.CharField(max_length=255, null=True, blank=True)),
                ('address_locality', models.CharField(max_length=255, null=True, blank=True)),
                ('address_region', models.CharField(max_length=255, null=True, blank=True)),
                ('address_postal_code', models.CharField(max_length=255, null=True, blank=True)),
                ('address_country', models.CharField(max_length=255, null=True, blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='token',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='code',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
