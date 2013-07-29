from django import forms
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from ietf.doc.models import *

def state_help(request, type):
    slug, title = {
        "draft-iesg": ("draft-iesg", "IESG States For Internet-Drafts"),
        "draft-rfceditor": ("draft-rfceditor", "RFC Editor States For Internet-Drafts"),
        "draft-iana-action": ("draft-iana-action", "IANA Action States For Internet-Drafts"),
        "charter": ("charter", "Charter States"),
        "conflict-review": ("conflrev", "Conflict Review States")
        }.get(type, (None, None))
    state_type = get_object_or_404(StateType, slug=slug)

    states = State.objects.filter(type=state_type).order_by("order")

    has_next_states = False
    for state in states:
        if state.next_states.all():
            has_next_states = True
            break

    tags = []

    if state_type.slug == "draft-iesg":
        # legacy hack
        states = list(states)
        fake_state = dict(name="I-D Exists",
                          desc="Initial (default) state for all internet drafts. Such documents are not being tracked by the IESG as no request has been made of the IESG to do anything with the document.",
                          next_states=dict(all=State.objects.filter(type="draft-iesg", slug__in=("watching", "pub-req")))
                          )
        states.insert(0, fake_state)

        tags = DocTagName.objects.filter(slug__in=IESG_SUBSTATE_TAGS)

    return render_to_response("doc/state_help.html", {
            "title": title,
            "state_type": state_type,
            "states": states,
            "has_next_states": has_next_states,
            "tags": tags,
            },
                              context_instance=RequestContext(request))
