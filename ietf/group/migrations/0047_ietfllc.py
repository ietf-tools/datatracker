# Copyright The IETF Trust 2021 All Rights Reserved

from django.db import migrations

def email(person):
    e = person.email_set.filter(primary=True).first()
    if not e:
        e = person.email_set.filter(active=True).order_by("-time").first()
    return e

def forward(apps, schema_editor):
    Group = apps.get_model('group', 'Group')
    Person = apps.get_model('person', 'Person')
    llc = Group.objects.create(
        acronym='ietfadminllc',
        name="IETF Administration LLC",
        state_id='active',
        type_id='adm',
        description="The IETF Administration LLC (IETF LLC) provides the corporate legal home for the IETF, the Internet Architecture Board (IAB), and the Internet Research Task Force (IRTF).  The Administration (https://www.ietf.org/about/administration/) section of the website has full details of the LLC and is where the various policies and reports produced by the LLC are published.",
    )
    Group.objects.filter(acronym='llc-board').update(parent=llc, description="The IETF Administration LLC (IETF LLC) provides the corporate legal home for the IETF, the Internet Architecture Board (IAB), and the Internet Research Task Force (IRTF).  The Administration (https://www.ietf.org/about/administration/) section of the website has full details of the LLC and is where the various policies and reports produced by the LLC are published.")
    llc_staff= Group.objects.create(
        acronym='llc-staff',
        name="IETF LLC employees",
        state_id='active',
        type_id='adm',
        parent=llc,
        description="The IETF Administration LLC (IETF LLC) provides the corporate legal home for the IETF, the Internet Architecture Board (IAB), and the Internet Research Task Force (IRTF).  The Administration (https://www.ietf.org/about/administration/) section of the website has full details of the LLC and is where the various policies and reports produced by the LLC are published.",
    )
    legal = Group.objects.create(
        acronym='legal-consult',
        name="Legal consultation group",
        state_id='active',
        type_id='adm',
        parent=llc,
        description="The legal-consult list is a group of community participants who provide their views to the IETF Administration LLC in private on various legal matters.  This was first established under the IAOC and has not been reviewed since.  Legal advice is provided separately to the LLC by contracted external counsel.",
    )

    for email_addr in ('jay@ietf.org', 'ghwood@ietf.org', 'lbshaw@ietf.org', 'krathnayake@ietf.org'):
        p = Person.objects.get(email__address=email_addr)
        llc_staff.role_set.create(name_id='member',person=p,email=email(p))

    for email_addr in (
        'amorris@amsl.com',
        'brad@biddle.law',
        'David.Wilson@thompsonhine.com',
        'glenn.deen@nbcuni.com',
        'hall@isoc.org',
        'Jason_Livingood@comcast.com',
        'jay@ietf.org',
        'jmh@joelhalpern.com',
        'johnl@taugh.com',
        'kathleen.moriarty.ietf@gmail.com',
        'lars@eggert.org',
        'lflynn@amsl.com',
        'stewe@stewe.org',
        'vigdis@biddle.law',
        'wendy@seltzer.org',
    ):
        p = Person.objects.filter(email__address=email_addr).first()
        if p:
            legal.role_set.create(name_id='member', person=p, email=email(p))


def reverse(apps, schema_editor):
    Group = apps.get_model('group', 'Group')
    Group.objects.filter(acronym='llc-board').update(parent=None)
    Group.objects.filter(acronym__in=['llc_staff','legal-consult']).delete()
    Group.objects.filter(acronym='ietfadminllc').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0046_grouptypename_admin_to_adm'),
        ('person', '0019_auto_20210604_1443'),
        # The below are needed for reverse migrations to work
        ('name','0028_iabasg'),
        ('doc', '0043_bofreq_docevents'),
        ('liaisons','0009_delete_liaisonstatementgroupcontacts_model'),
        ('meeting', '0018_document_primary_key_cleanup'),
        ('review', '0014_document_primary_key_cleanup'),
        ('submit', '0008_submissionextresource'), 
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
