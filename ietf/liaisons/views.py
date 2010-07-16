# Copyright The IETF Trust 2007, All Rights Reserved
from django.shortcuts import render_to_response
from django.template import RequestContext

from ietf.liaisons.decorators import can_submit_liaison
from ietf.liaisons.forms import LiaisonForm


@can_submit_liaison
def add_liaison(request):
    form = LiaisonForm(request.user)

    return render_to_response(
        'liaisons/liaisondetail_edit.html',
        {'form': form},
        context_instance=RequestContext(request),
    )
