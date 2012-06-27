import sys
import datetime

from django.core.management.base import BaseCommand

from ietf.community.models import Rule, CommunityList


class Command(BaseCommand):
    help = (u"Update drafts in community lists by reviewing their rules")


    def handle(self, *args, **options):
        now = datetime.datetime.now()
        
        rules = Rule.objects.filter(last_updated__lt=now - datetime.timedelta(hours=12))
        count = rules.count()
        index = 1
        for rule in rules:
            sys.stdout.write('Updating rule [%s/%s]\r' % (index, count))
            sys.stdout.flush()
            rule.save()
            index += 1
        if index > 1:
            print
        cls = CommunityList.objects.filter(cached__isnull=False)
        count = cls.count()
        index = 1
        for cl in cls:
            sys.stdout.write('Clearing community list cache [%s/%s]\r' % (index, count))
            sys.stdout.flush()
            cl.cached = None
            cl.save()
            index += 1
        if index > 1:
            print
