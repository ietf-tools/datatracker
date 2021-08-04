# Copyright The IETF Trust 2021 All Rights Reserved

import os

from django.conf import settings
from django.core.management.base import BaseCommand

from ietf.doc.utils import generate_idnits2_rfcs_obsoleted
from ietf.utils.log import log

class Command(BaseCommand):
    help = ('Generate the rfcs-obsoleted file used by idnits2')

    def handle(self, *args, **options):
        filename=os.path.join(settings.DERIVED_DIR,'idnits2-rfcs-obsoleted')
        blob = generate_idnits2_rfcs_obsoleted()
        try:
            bytes = blob.encode('utf-8')
            with open(filename,'wb') as f:
                f.write(bytes)
        except Exception as e:
            log('failed to write idnits2-rfcs-obsoleted: '+str(e))
            raise e
