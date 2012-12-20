from ietf.doc.models import *

def find_discrepancies():
    res = []

    title = "Drafts that have been sent to the RFC Editor but do not have an RFC Editor state"

    docs = Document.objects.filter(states__in=list(State.objects.filter(type="draft-iesg", slug__in=("ann", "rfcqueue")))).exclude(states__in=list(State.objects.filter(type="draft-rfceditor")))

    res.append((title, docs))

    title = "Drafts that have the IANA Action state \"In Progress\" but do not have a \"IANA\" RFC-Editor state/tag"

    docs = Document.objects.filter(states__in=list(State.objects.filter(type="draft-iana-action", slug__in=("inprog",)))).exclude(tags="iana").exclude(states__in=list(State.objects.filter(type="draft-rfceditor", slug="iana")))

    res.append((title, docs))

    title = "Drafts that have the IANA Action state \"Waiting on RFC Editor\" or \"RFC-Ed-Ack\" but are in the RFC Editor state \"IANA\"/tagged with \"IANA\""

    docs = Document.objects.filter(states__in=list(State.objects.filter(type="draft-iana-action", slug__in=("waitrfc", "rfcedack")))).filter(models.Q(tags="iana") | models.Q(states__in=list(State.objects.filter(type="draft-rfceditor", slug="iana"))))

    res.append((title, docs))

    title = "Drafts that have a state other than \"RFC Ed Queue\", \"RFC Published\" or \"Sent to the RFC Editor\" and have an RFC Editor or IANA Action state"

    docs = Document.objects.exclude(states__in=list(State.objects.filter(type="draft-iesg", slug__in=("rfcqueue", "pub"))) + list(State.objects.filter(type__in=("draft-stream-iab", "draft-stream-ise", "draft-stream-irtf"), slug="rfc-edit"))).filter(states__in=list(State.objects.filter(type__in=("draft-iana-action", "draft-rfceditor"))))

    res.append((title, docs))

    for _, docs in res:
        for d in docs:
            d.iesg_state = d.get_state("draft-iesg")
            d.rfc_state = d.get_state("draft-rfceditor")
            d.iana_action_state = d.get_state("draft-iana-action")

    return res

