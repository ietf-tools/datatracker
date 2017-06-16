# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def populate_names(apps, schema_editor):
    # LiaisonStatementState: Pending, Approved, Dead
    LiaisonStatementState = apps.get_model("name", "LiaisonStatementState")
    LiaisonStatementState.objects.create(slug="pending", order=1, name="Pending")
    LiaisonStatementState.objects.create(slug="approved", order=2, name="Approved")
    LiaisonStatementState.objects.create(slug="posted", order=3, name="Posted")
    LiaisonStatementState.objects.create(slug="dead", order=4, name="Dead")

    # LiaisonStatementEventTypeName: Submitted, Modified, Approved, Posted, Killed, Resurrected, MsgIn, MsgOut, Comment
    LiaisonStatementEventTypeName = apps.get_model("name", "LiaisonStatementEventTypeName")
    LiaisonStatementEventTypeName.objects.create(slug="submitted", order=1, name="Submitted")
    LiaisonStatementEventTypeName.objects.create(slug="modified", order=2, name="Modified")
    LiaisonStatementEventTypeName.objects.create(slug="approved", order=3, name="Approved")
    LiaisonStatementEventTypeName.objects.create(slug="posted", order=4, name="Posted")
    LiaisonStatementEventTypeName.objects.create(slug="killed", order=5, name="Killed")
    LiaisonStatementEventTypeName.objects.create(slug="resurrected", order=6, name="Resurrected")
    LiaisonStatementEventTypeName.objects.create(slug="msgin", order=7, name="MsgIn")
    LiaisonStatementEventTypeName.objects.create(slug="msgout", order=8, name="MsgOut")
    LiaisonStatementEventTypeName.objects.create(slug="comment", order=9, name="Comment")

    #LiaisonStatementTagName: Action Required, Action Taken
    LiaisonStatementTagName = apps.get_model("name", "LiaisonStatementTagName")
    LiaisonStatementTagName.objects.create(slug="required", order=1, name="Action Required")
    LiaisonStatementTagName.objects.create(slug="taken", order=2, name="Action Taken")

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0006_add_liaison_names'),
    ]

    operations = [
        migrations.RunPython(populate_names),
    ]
