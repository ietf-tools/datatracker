# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


"""
Functions to aid unit testing
"""
from ietf.person.models import Person
from ietf.group.models import Role


def reset():
    """Revert my roles back to production settings"""
    me = Person.objects.get(name="Ryan Cross")
    me.role_set.all().delete()
    Role.objects.create(
        person=me, email_id="rcross@amsl.com", name_id="secr", group_id=4
    )
    print(me.role_set.all())


def copy_roles(person):
    """Copy the roles of person"""
    me = Person.objects.get(name="Ryan Cross")
    me.role_set.all().delete()
    for role in person.role_set.all():
        Role.objects.create(
            person=me, email_id="rcross@amsl.com", name=role.name, group=role.group
        )
    print(me.role_set.all())
