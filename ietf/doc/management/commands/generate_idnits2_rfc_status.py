# Copyright The IETF Trust 2021 All Rights Reserved

import os

from django.conf import settings
from django.core.management.base import BaseCommand

from ietf.doc.utils import generate_idnits2_rfc_status
from ietf.utils.log import log

class Command(BaseCommand):
    help = ('Generate the rfc_status blob used by idnits2')

    def handle(self, *args, **options):
        filename=os.path.join(settings.DERIVED_DIR,'idnits2-rfc-status')
        blob = generate_idnits2_rfc_status()
        try:
            bytes = blob.encode('utf-8')
            with open(filename,'wb') as f:
                f.write(bytes)
        except Exception as e:
            log('failed to write idnits2-rfc-status: '+str(e))
            raise e
