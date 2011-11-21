from redesign.doc.models import *

def get_state_types(doc):
    res = []

    if not doc:
        return res
    
    res.append(doc.type_id)

    #if doc.type_id in ("agenda", "minutes", "slides", "liai-att"):
    #    res.append(doc.type_id)
    if doc.type_id == "draft":
        if doc.stream_id != "legacy":
            res.append("draft-stream-%s" % doc.stream_id)

        res.append("draft-iesg")
        res.append("draft-iana")
        res.append("draft-rfceditor")
        
    return res

def get_tags_for_stream_id(stream_id):
    if stream_id == "ietf":
        return ["w-expert", "w-extern", "w-merge", "need-aut", "w-refdoc", "w-refing", "rev-wglc", "rev-ad", "rev-iesg", "sheph-u", "other"]
    elif stream_id == "iab":
        return ["need-ed", "w-part", "w-review", "need-rev", "sh-f-up"]
    elif stream_id == "irtf":
        return ["need-ed", "need-sh", "w-dep", "need-rev", "iesg-com"]
    elif stream_id == "ise":
        return ["w-dep", "w-review", "need-rev", "iesg-com"]
    else:
        return []

def active_ballot_positions(doc):
    """Return dict mapping each active AD to a current ballot position (or None if they haven't voted)."""
    active_ads = list(Person.objects.filter(role__name="ad", role__group__state="active"))
    res = {}

    positions = BallotPositionDocEvent.objects.filter(doc=doc, type="changed_ballot_position", ad__in=active_ads).select_related('ad').order_by("-time", "-id")

    for pos in positions:
        if pos.ad not in res:
            res[pos.ad] = pos

    for ad in active_ads:
        if ad not in res:
            res[ad] = None

    return res
    
