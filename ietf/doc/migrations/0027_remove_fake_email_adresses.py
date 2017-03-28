# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def fix_invalid_emails(apps, schema_editor):
    Email = apps.get_model("person", "Email")
    Role = apps.get_model("group", "Role")
    RoleHistory = apps.get_model("group", "RoleHistory")
    DocumentAuthor = apps.get_model("doc", "DocumentAuthor")
    DocHistoryAuthor = apps.get_model("doc", "DocHistoryAuthor")

    e = Email.objects.filter(address="unknown-email-Gigi-Karmous-Edwards").first()
    if e:
        # according to ftp://ietf.org/ietf/97dec/adsl-minutes-97dec.txt
        new_e, _ = Email.objects.get_or_create(
            address="GiGi.Karmous-Edwards@pulse.com",
            primary=e.primary,
            active=e.active,
            person=e.person,
        )
        Role.objects.filter(email=e).update(email=new_e)
        RoleHistory.objects.filter(email=e).update(email=new_e)
        e.delete()

    e = Email.objects.filter(address="unknown-email-Pat-Thaler").first()
    if e:
        # current chair email
        new_e = Email.objects.get(address="pat.thaler@broadcom.com")
        Role.objects.filter(email=e).update(email=new_e)
        RoleHistory.objects.filter(email=e).update(email=new_e)
        e.delete()

    e = Email.objects.filter(address="unknown-email-Greg-<gregimirsky@gmail.com>>").first()
    if e:
        # current email
        new_e = Email.objects.get(address="gregimirsky@gmail.com")
        DocumentAuthor.objects.filter(email=e).update(email=new_e)
        DocHistoryAuthor.objects.filter(email=e).update(email=new_e)
        e.delete()

    DocumentAuthor.objects.filter(email__address__startswith="unknown-email-").exclude(email__address__contains="@").update(email=None)
    DocHistoryAuthor.objects.filter(email__address__startswith="unknown-email-").exclude(email__address__contains="@").update(email=None)
    Email.objects.exclude(address__contains="@").filter(address__startswith="unknown-email-").delete()

    assert not Email.objects.filter(address__startswith="unknown-email-")

class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0026_author_revamp_and_extra_attributes'),
        ('person', '0014_auto_20160613_0751'),
        ('group', '0009_auto_20150930_0758'),
    ]

    operations = [
        migrations.RunPython(fix_invalid_emails, migrations.RunPython.noop),
    ]
