# Copyright The IETF Trust 2022, All Rights Reserved

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('person', '0024_pronouns'),
    ]

    operations = [
        migrations.AlterField(
            model_name='personalapikey',
            name='endpoint',
            field=models.CharField(choices=[('/api/appauth/authortools', '/api/appauth/authortools'), ('/api/appauth/bibxml', '/api/appauth/bibxml'), ('/api/iesg/position', '/api/iesg/position'), ('/api/meeting/session/video/url', '/api/meeting/session/video/url'), ('/api/notify/meeting/bluesheet', '/api/notify/meeting/bluesheet'), ('/api/notify/meeting/registration', '/api/notify/meeting/registration'), ('/api/notify/session/attendees', '/api/notify/session/attendees'), ('/api/notify/session/chatlog', '/api/notify/session/chatlog'), ('/api/notify/session/polls', '/api/notify/session/polls'), ('/api/v2/person/person', '/api/v2/person/person')], max_length=128),
        ),
    ]
