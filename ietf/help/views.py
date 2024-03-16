# Copyright The IETF Trust 2007, All Rights Reserved

import debug                            # pyflakes:ignore

from ietf.name.models import StreamName
from django.shortcuts import redirect

# These are just redirects to the new URLs under /doc; can probably go away eventually.

def state_index(request):
    return redirect('/doc/help/state/', permanent = True)

def state(request, doc, type=None):
    if type:
        streams = [ s.slug for s in StreamName.objects.all() ]
        if type in streams:
            type = "stream-%s" % type
    slug = "%s-%s" % (doc,type) if type else doc
    return redirect('/doc/help/state/%s' % slug, permanent = True)
    