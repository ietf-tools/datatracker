from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import Http404

from ietf.doc.models import State, StateType, IESG_SUBSTATE_TAGS
from ietf.name.models import DocRelationshipName,  DocTagName
from ietf.doc.utils import get_tags_for_stream_id

def state_help(request, type):
    slug, title = {
        "draft-iesg": ("draft-iesg", "IESG States for Internet-Drafts"),
        "draft-rfceditor": ("draft-rfceditor", "RFC Editor States for Internet-Drafts"),
        "draft-iana-action": ("draft-iana-action", "IANA Action States for Internet-Drafts"),
        "draft-stream-ietf": ("draft-stream-ietf", "IETF Stream States for Internet-Drafts"),
        "draft-stream-irtf": ("draft-stream-irtf", "IRTF Stream States for Internet-Drafts"),
        "draft-stream-ise": ("draft-stream-ise", "ISE Stream States for Internet-Drafts"),
        "draft-stream-iab": ("draft-stream-iab", "IAB Stream States for Internet-Drafts"),
        "charter": ("charter", "Charter States"),
        "conflict-review": ("conflrev", "Conflict Review States"),
        "status-change": ("statchg", "RFC Status Change States"),
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
    elif state_type.slug.startswith("draft-stream-"):
        possible = get_tags_for_stream_id(state_type.slug.replace("draft-stream-", ""))
        tags = DocTagName.objects.filter(slug__in=possible)

    return render_to_response("doc/state_help.html", {
            "title": title,
            "state_type": state_type,
            "states": states,
            "has_next_states": has_next_states,
            "tags": tags,
            },
                              context_instance=RequestContext(request))

def relationship_help(request,subset=None):
    subsets = { "reference": ['refnorm','refinfo','refunk','refold'],
                "status" : ['tops','tois','tohist','toinf','tobcp','toexp'],
              }
    if subset and subset not in subsets:
        raise Http404()
    rels = DocRelationshipName.objects.filter(used=True)
    if subset:
       rels = rels.filter(slug__in=subsets[subset]) 
    return render_to_response("doc/relationship_help.html", {
               "relations": rels
              },
                              context_instance=RequestContext(request))
