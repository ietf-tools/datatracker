# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf import settings
from ietf.secr import __date__, __rev__, __version__, __id__

def server_mode(request):
    return {'server_mode': settings.SERVER_MODE}
    
def secr_revision_info(request):
    return {'secr_revision_time': __date__[7:32], 'secr_revision_date': __date__[7:17], 'secr_revision_num': __rev__[6:-2], "secr_revision_id": __id__[5:-2], "secr_version_num": __version__ }

def static(request):
    return {'SECR_STATIC_URL': settings.SECR_STATIC_URL}
