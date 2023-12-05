# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def markdown_names(apps, schema_editor):
    ImportantDateName = apps.get_model("name", "ImportantDateName")
    changes = [
        ('bofproposals', "Preliminary BOF proposals requested. To request a __BoF__ session use the [IETF BoF Request Tool](/doc/bof-requests)."),
        ('openreg', "IETF Online Registration Opens [Register Here](https://www.ietf.org/how/meetings/register/)."),
        ('opensched', "Working Group and BOF scheduling begins. To request a Working Group session, use the [IETF Meeting Session Request Tool](/secr/sreq/). If you are working on a BOF request, it is highly recommended to tell the IESG now by sending an [email to iesg@ietf.org](mailtp:iesg@ietf.org) to get advance help with the request."),
        ('cutoffwgreq', "Cut-off date for requests to schedule Working Group Meetings at UTC 23:59. To request a __Working Group__ session, use the [IETF Meeting Session Request Tool](/secr/sreq/)."),
        ('idcutoff', "Internet-Draft submission cut-off (for all Internet-Drafts, including -00) by UTC 23:59. Upload using the [I-D Submission Tool](/submit/)."),
        ('cutoffwgreq', "Cut-off date for requests to schedule Working Group Meetings at UTC 23:59. To request a __Working Group__ session, use the [IETF Meeting Session Request Tool](/secr/sreq/)."),
        ('bofprelimcutoff', "Cut-off date for BOF proposal requests. To request a __BoF__ session use the [IETF BoF Request Tool](/doc/bof-requests)."),
        ('cutoffbofreq', "Cut-off date for BOF proposal requests to Area Directors at UTC 23:59. To request a __BoF__ session use the [IETF BoF Request Tool](/doc/bof-requests)."),
    ]
    for slug, newDescription in changes:
        datename = ImportantDateName.objects.get(pk=slug) # If the slug does not exist, then Django will throw an exception :-)
        datename.desc = newDescription
        datename.save()

class Migration(migrations.Migration):
    dependencies = [
        ("name", "0011_subseries"),
    ]

    operations = [
        migrations.RunPython(markdown_names),
    ]
