# Copyright The IETF Trust 2020, All Rights Reserved
import json

from django.core.management.base import BaseCommand

from ietf.extresource.models import ExtResource
from ietf.doc.models import DocExtResource
from ietf.group.models import GroupExtResource
from ietf.person.models import PersonExtResource

class Command(BaseCommand):
    help = ('Locate information about gihub repositories to backup')

    def handle(self, *args, **options):

        info_dict = {}
        for repo in ExtResource.objects.filter(name__slug='github_repo'):
            if repo not in info_dict:
                info_dict[repo.value] = []

            for username in DocExtResource.objects.filter(extresource__name__slug='github_username', doc__name__in=repo.docextresource_set.values_list('doc__name',flat=True).distinct()):
                info_dict[repo.value].push(username.value)

            for username in GroupExtResource.objects.filter(extresource__name__slug='github_username', group__acronym__in=repo.groupextresource_set.values_list('group__acronym',flat=True).distinct()):
                info_dict[repo.value].push(username.value)

            for username in PersonExtResource.objects.filter(extresource__name__slug='github_username', person_id__in=repo.personextresource_set.values_list('person__id',flat=True).distinct()):
                info_dict[repo.value].push(username.value)

        print (json.dumps(info_dict))
