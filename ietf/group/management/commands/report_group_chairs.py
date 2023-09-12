# Copyright The IETF Trust 2023, All Rights Reserved

from django.core.management.base import BaseCommand

from ietf.group.models import Group
from ietf.group.utils import role_change_history

class Command(BaseCommand):

    def handle(self, *args, **options):

        interesting_types = ["wg","ag","rg","rag","edwg"]
        for type in interesting_types:
            groups = Group.objects.filter(type_id=type,state="active").order_by('acronym')
            parent = groups.first().parent
            print(f"{parent.name} {groups.first().type.verbose_name}")
            for group in groups:
                print(f"    {group.acronym} - {group.name}")
                history = role_change_history(group.acronym, "chair")
                for time in sorted(history, reverse=True):
                    print(f"        {time:%Y-%m-%d}: {', '.join(history[time])}")

