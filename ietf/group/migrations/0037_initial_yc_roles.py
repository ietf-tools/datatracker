# Copyright The IETF Trust 2020 All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    RoleName = apps.get_model('name','RoleName')
    Group = apps.get_model('group','Group')
    Role = apps.get_model('group','Role')
    Person = apps.get_model('person','Person')

    RoleName.objects.create(
        slug = 'yc_operator',
        name = 'YangCatalog Operator',
        desc = 'Can grant user api rights and browse the YangCatalog directory structure',
    )

    ycsupport = Group.objects.create(
        acronym='ycsupport',
        name="YangCatalog Support",
        state_id='active',
        type_id='team',
        parent = Group.objects.get(acronym='ops'),
        description = "Team for supporting YangCatalog.org operations",
    )

    RoleName.objects.create(
        slug = 'yc_admin',
        name = 'YangCatalog Administrator',
        desc = 'Can operate the YangCatalog, change its configuration, and edit its data',
    )

    for name,role_name_id in (
        ('Robert Sparks','yc_operator'),
        ('Benoit Claise','yc_operator'),
        ('Eric Vyncke','yc_operator'),
        ('Miroslav Kovac','yc_admin'),
        ('Slavomir Mazur','yc_admin'),
    ):
        person = Person.objects.get(name=name)
        email = person.email_set.filter(primary=True).first()
        if not email:
            email = person.email_set.filter(active=True).order_by("-time").first()
        Role.objects.create(
            name_id = role_name_id,
            group = ycsupport,
            person = person,
            email = email,
        )

def reverse(apps, schema_editor):
    RoleName = apps.get_model('name','RoleName')
    Group = apps.get_model('group','Group')
    Role = apps.get_model('group','Role')

    Role.objects.filter(name_id__in = ( 'yc_operator' , 'yc_admin' )).delete()
    Group.objects.filter(acronym='ycsupport').delete()
    RoleName.objects.filter(slug__in=( 'yc_operator' , 'yc_admin' )).delete() 


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0036_orgs_vs_repos'),
        ('name', '0020_add_rescheduled_session_name'),
        ('person','0016_auto_20200807_0750'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
