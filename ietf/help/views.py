# Copyright The IETF Trust 2007, All Rights Reserved

from django.template import RequestContext
from django.shortcuts import get_object_or_404, render_to_response

import debug

from ietf.doc.models import State, StateType


def state(request, doc, type=None):
    slug = "%s-%s" % (doc,type) if type else doc
    debug.show('slug')
    statetype = get_object_or_404(StateType, slug=slug)
    states = State.objects.filter(used=True, type=statetype).order_by('order')
    return render_to_response('help/states.html', {"doc": doc, "type": statetype, "states":states},
        context_instance=RequestContext(request))

