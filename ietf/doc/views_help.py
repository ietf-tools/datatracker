# Copyright The IETF Trust 2013-2023, All Rights Reserved

import debug # pyflakes: ignore

from django.shortcuts import render, get_object_or_404
from django.http import Http404

from ietf.doc.models import State, StateType, IESG_SUBSTATE_TAGS
from ietf.name.models import DocRelationshipName,  DocTagName
from ietf.doc.utils import get_tags_for_stream_id

def state_index(request):
    types = StateType.objects.all()
    names = [ type.slug for type in types ]
    for type in types:
        if "-" in type.slug and type.slug.split('-',1)[0] in names:
            type.stategroups = None
        else:
            groups = StateType.objects.filter(slug__startswith=type.slug)
            type.stategroups =  [ g.slug[len(type.slug)+1:] for g in groups if not g == type ] or ""
                
    return render(request, 'doc/state_index.html', {"types": types})

def state_help(request, type=None):
    slug, title = {
        "draft-iesg": ("draft-iesg", "IESG States for Internet-Drafts"),
        "draft-rfceditor": ("draft-rfceditor", "RFC Editor States for Internet-Drafts"),
        "draft-iana-action": ("draft-iana-action", "IANA Action States for Internet-Drafts"),
        "draft-iana-review": ("draft-iana-review", "IANA Review States for Internet-Drafts"),
        "draft-iana-experts": ("draft-iana-experts", "IANA Expert Review States for Internet-Drafts"),
        "draft-stream-ietf": ("draft-stream-ietf", "IETF Stream States for Internet-Drafts"),
        "draft-stream-irtf": ("draft-stream-irtf", "IRTF Stream States for Internet-Drafts"),
        "draft-stream-ise": ("draft-stream-ise", "ISE Stream States for Internet-Drafts"),
        "draft-stream-iab": ("draft-stream-iab", "IAB Stream States for Internet-Drafts"),
        "draft-stream-editorial": ("draft-stream-editorial", "Editorial Stream States for Internet-Drafts"),
        "charter": ("charter", "Charter States"),
        "conflict-review": ("conflrev", "Conflict Review States"),
        "status-change": ("statchg", "RFC Status Change States"),
        "bofreq": ("bofreq", "BOF Request States"),
        "procmaterials": ("procmaterials", "Proceedings Materials States"),
        "statement": ("statement", "Statement States"),
        "slides": ("slides", "Slides States"),
        "minutes": ("minutes", "Minutes States"),
        "liai-att": ("liai-att", "Liaison Attachment States"),
        "recording": ("recording", "Recording States"),
        "bluesheets": ("bluesheets", "Bluesheets States"),
        "reuse_policy": ("reuse_policy", "Reuse Policy States"),
        "review": ("review", "Review States"),
        "liaison": ("liaison", "Liaison States"),
        "shepwrit": ("shepwrit", "Shapherd Writeup States"),
        "bofreq": ("bofreq", "BOF Request States"),
        "procmaterials": ("procmaterials", "Proceedings Materials States"),
        "chatlog": ("chatlog", "Chat Log States"),
        "polls": ("polls", "Polls States"),
        "statement": ("statement", "Statement States"),
        "rfc": ("rfc", "RFC States"),
        "bcp": ("bcp", "BCP States"),
        "std": ("std", "STD States"),
        "fyi": ("fyi", "FYI States"),
        "narrativeminutes": ("narrativeminutes", "Narrative Minutes States"),
        "draft": ("draft", "Draft States"),
        "statchg": ("statchg", "Status Change States"),
        "agenda": ("agenda", "Agenda States"),
        "conflrev": ("conflrev", "Conflict Review States")
        }.get(type, (None, None))
    state_type = get_object_or_404(StateType, slug=slug)

    states = State.objects.filter(used=True, type=state_type).order_by("order")

    has_next_states = False
    for state in states:
        if state.next_states.all():
            has_next_states = True
            break

    tags = []

    if state_type.slug == "draft-iesg":
        tags = DocTagName.objects.filter(slug__in=IESG_SUBSTATE_TAGS)
    elif state_type.slug.startswith("draft-stream-"):
        possible = get_tags_for_stream_id(state_type.slug.replace("draft-stream-", ""))
        tags = DocTagName.objects.filter(slug__in=possible)

    return render(request, "doc/state_help.html",
                           {
                               "title": title,
                               "state_type": state_type,
                               "states": states,
                               "has_next_states": has_next_states,
                               "tags": tags,
                           } )

def relationship_help(request,subset=None):
    subsets = { "reference": ['refnorm','refinfo','refunk','refold'],
                "status" : ['tops','tois','tohist','toinf','tobcp','toexp'],
              }
    if subset and subset not in subsets:
        raise Http404()
    rels = DocRelationshipName.objects.filter(used=True)
    if subset:
       rels = rels.filter(slug__in=subsets[subset]) 
    return render(request, "doc/relationship_help.html", { "relations": rels } )
