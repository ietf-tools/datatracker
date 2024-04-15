# Copyright The IETF Trust 2007, All Rights Reserved

import debug                            # pyflakes:ignore

from ietf.name.models import StreamName
from django.shortcuts import redirect

# This is just a redirect to the new URL under /doc; can probably go away eventually.

def state(request, doc, type=None):
    if type:
        streams = [ s.slug for s in StreamName.objects.all() ]
        if type in streams:
            type = "stream-%s" % type
    slug = "%s-%s" % (doc,type) if type else doc
    return redirect('/doc/help/state/%s' % slug, permanent = True)
    