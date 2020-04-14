# Copyright The IETF Trust 2019-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os

from collections import Counter

from django.core.management.base import BaseCommand

from ietf.doc.models import DocEvent
from ietf.meeting.models import Meeting, SessionPresentation
from ietf.person.models import Person

from ietf.secr.proceedings.proc_utils import is_powerpoint, post_process

class Command(BaseCommand):
    help = ('Fix uploaded_filename and generate pdf from pptx')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', dest='dry-run', default=False, help='Report on changes that would be made without making them')

    def handle(self, *args, **options):
        ietf105 = Meeting.objects.get(number=105)
        slides_path = os.path.join(ietf105.get_materials_path(),'slides')
        system_person = Person.objects.get(name="(System)")
        counts = Counter()

        for sp in SessionPresentation.objects.filter(session__meeting__number=105,document__type='slides'): #.filter(document__name='slides-105-manet-dlep-multicast-support-discussion'):
            slides = sp.document
            if not os.path.exists(os.path.join(slides_path,slides.uploaded_filename)):
                name, ext = os.path.splitext(slides.uploaded_filename)
                target_filename = '%s-%s%s' % (name[:name.rfind('-ss')], slides.rev,ext)
                if os.path.exists(os.path.join(slides_path,target_filename)):
                    slides.uploaded_filename = target_filename
                    if not options['dry-run']:
                        e = DocEvent.objects.create(doc=slides, rev=slides.rev, by=system_person, type='changed_document', desc='Corrected uploaded_filename')
                        slides.save_with_history([e])
                    counts['uploaded_filename repair succeeded'] += 1

                else:
                    self.stderr.write("Unable to repair %s" % slides)
                    counts['uploaded_filename repair failed'] += 1
                    continue
            else:
                counts['uploaded_filename already ok'] += 1

            if is_powerpoint(slides): 
                base, _ = os.path.splitext(slides.uploaded_filename)
                if os.path.exists(os.path.join(slides_path,base+'.pdf')):
                    self.stderr.write("PDF already exists for %s " % slides)
                    counts['PDF already exists for a repaired file'] += 1
                else:
                    if not options['dry-run']:
                        post_process(slides)
                    counts['PDF conversions'] += 1

        if options['dry-run']:
            self.stdout.write("This is a dry-run. Nothing has actually changed. In a normal run, the output would say the following:")

        for label,count in counts.iteritems():
            self.stdout.write("%s : %d" % (label,count) )


