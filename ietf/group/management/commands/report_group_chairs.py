# Copyright The IETF Trust 2023, All Rights Reserved

from django.core.management.base import BaseCommand

from ietf.group.models import Group
from ietf.group.utils import role_change_history

class Command(BaseCommand):

    def handle(self, *args, **options):

        interesting_types = ["wg","ag","rg","rag","edwg"]
        for type in interesting_types:
            seen_parent = None
            groups = Group.objects.filter(type_id=type,state="active").order_by('parent__acronym','acronym')
            for group in groups:
                if group.parent != seen_parent:
                    print(f"{group.parent.name} {group.type.verbose_name}")
                    seen_parent = group.parent
                print(f"    {group.acronym} - {group.name}")
                history = role_change_history(group.acronym, "chair")
                for time in sorted(history, reverse=True):
                    print(f"        {time:%Y-%m-%d}: {', '.join(history[time])}")

