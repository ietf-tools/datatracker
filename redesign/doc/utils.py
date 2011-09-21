from redesign.doc.models import *

def get_state_types(doc):
    res = []

    if not doc:
        return res
    
    res.append(doc.type_id)
    #if doc.type_id in ("agenda", "minutes", "slides", "liai-att"):
    #    res.append(doc.type_id)
    if doc.type_id == "draft":
        if doc.stream_id == "ietf":
            wg_specific = doc.type_id + ":" + "wg" + ":" + doc.group.acronym
            if State.objects.filter(type=wg_specific):
                res.append(wg_specific)
            else:
                res.append(doc.type_id + ":" + "wg")
        elif doc.stream_id == "irtf":
            res.append(doc.type_id + ":" + "rg")
        elif doc.stream_id == "iab":
            res.append(doc.type_id + ":" + "iab")
        elif doc.stream_id == "ise":
            res.append(doc.type_id + ":" + "ise")

        res.append(doc.type_id + ":" + "iesg")
        res.append(doc.type_id + ":" + "iana")
        res.append(doc.type_id + ":" + "rfc-editor")
        
    return res


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
    
