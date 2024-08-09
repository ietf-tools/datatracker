# Copyright The IETF Trust 2023, All Rights Reserved

import csv

from sys import stdout

from django.core.management.base import BaseCommand

from ietf.group.models import Group
from ietf.group.utils import role_since

class Command(BaseCommand):

    def handle(self, *args, **options):
        interesting_types = ["wg","ag","rg","rag","edwg"]
        writer = csv.writer(stdout)
        for group in Group.objects.filter(type_id__in=interesting_types, state="active").order_by("parent__acronym","type_id","acronym"):
            roles = role_since(group.acronym, "chair")
            for role in roles:
                writer.writerow([group.parent.acronym, group.type_id, group.acronym, role.name, f"{role.time:%Y-%m-%d}"])
