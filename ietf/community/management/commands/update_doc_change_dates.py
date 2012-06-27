import sys

from django.core.management.base import BaseCommand
from django.db.models import Q

from ietf.community.constants import SIGNIFICANT_STATES
from ietf.community.models import DocumentChangeDates
from redesign.doc.models import Document


class Command(BaseCommand):
    help = (u"Update drafts in community lists by reviewing their rules")

    def handle(self, *args, **options):
        documents = Document.objects.filter(Q(type__name='Draft') | Q(states__name='rfc')).distinct()
        index = 1
        total = documents.count()

        for doc in documents:
            (changes, created) = DocumentChangeDates.objects.get_or_create(document=doc)
            new_version = doc.latest_event(type='new_revision')
            normal_change = doc.latest_event()
            significant_change = None
            for event in doc.docevent_set.filter(type='changed_document'):
                for state in SIGNIFICANT_STATES:
                    if ('<b>%s</b>' % state) in event.desc:
                        significant_change = event
                        break

            changes.new_version_date = new_version and new_version.time.date()
            changes.normal_change_date = normal_change and normal_change.time.date()
            changes.significant_change_date = significant_change and significant_change.time.date()

            changes.save()

            sys.stdout.write('Document %s/%s\r' % (index, total))
            sys.stdout.flush()
            index += 1
        print
