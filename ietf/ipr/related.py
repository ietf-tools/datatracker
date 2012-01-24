# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf import settings
from django.db.models import Q
from ietf.idtracker.models import InternetDraft, Rfc

inverse = {
            'updates': 'is_updated_by',
            'is_updated_by': 'updates',
            'obsoletes': 'is_obsoleted_by',
            'is_obsoleted_by': 'obsoletes',
            'replaces': 'is_replaced_by',
            'is_replaced_by': 'replaces',            
            'is_rfc_of': 'is_draft_of',
            'is_draft_of': 'is_rfc_of',
        }

display_relation = {
            'updates':          'that updated',
            'is_updated_by':    'that was updated by',
            'obsoletes':        'that obsoleted',
            'is_obsoleted_by':  'that was obsoleted by',
            'replaces':         'that replaced',
            'is_replaced_by':   'that was replaced by',
            'is_rfc_of':        'which came from',
            'is_draft_of':      'that was published as',
        }

def set_related(obj, rel, target):
    #print obj, rel, target
    # remember only the first relationship we find.
    if not hasattr(obj, "related"):
        obj.related = target
        obj.relation = display_relation[rel]
    return obj

def set_relation(first, rel, second):
    set_related(first, rel, second)
    set_related(second, inverse[rel], first)

def related_docs(doc, found = []):    
    """Get a list of document related to the given document.
    """
    #print "\nrelated_docs(%s, %s)" % (doc, found) 
    found.append(doc)
    if isinstance(doc, Rfc):
        try:
            item = InternetDraft.objects.get(rfc_number=doc.rfc_number)
            if not item in found:
                set_relation(doc, 'is_rfc_of', item)
                found = related_docs(item, found)
        except InternetDraft.DoesNotExist:
            pass
        for entry in doc.updated_or_obsoleted_by.all():
            item = entry.rfc
            if not item in found:
                action = inverse[entry.action.lower()]
                set_relation(doc, action, item)
                found = related_docs(item, found)
        for entry in doc.updates_or_obsoletes.all():
            item = entry.rfc_acted_on
            if not item in found:
                action = entry.action.lower()
                set_relation(doc, action, item)
                found = related_docs(item, found)
    if isinstance(doc, InternetDraft):
        if doc.replaced_by_id:
            item = doc.replaced_by
            if not item in found:
                set_relation(doc, 'is_replaced_by', item)
                found = related_docs(item, found)
        for item in doc.replaces_set.all():
            if not item in found:
                set_relation(doc, 'replaces', item)
                found = related_docs(item, found)
        if doc.rfc_number:
            item = Rfc.objects.get(rfc_number=doc.rfc_number)
            if not item in found:
                set_relation(doc, 'is_draft_of', item)
                found = related_docs(item, found)
    return found

def related_docsREDESIGN(alias, _):
    """Get related document aliases to given alias through depth-first search."""
    from ietf.doc.models import RelatedDocument
    from ietf.doc.proxy import DraftLikeDocAlias

    mapping = dict(
        updates='that updated',
        obs='that obsoleted',
        replaces='that replaced',
        )
    inverse_mapping = dict(
        updates='that was updated by',
        obs='that was obsoleted by',
        replaces='that was replaced by',
        )
    
    res = [ alias ]
    remaining = [ alias ]
    while remaining:
        a = remaining.pop()
        related = RelatedDocument.objects.filter(relationship__in=mapping.keys()).filter(Q(source=a.document) | Q(target=a))
        for r in related:
            if r.source == a.document:
                found = DraftLikeDocAlias.objects.filter(pk=r.target_id)
                inverse = True
            else:
                found = DraftLikeDocAlias.objects.filter(document=r.source)
                inverse = False

            for x in found:
                if not x in res:
                    x.related = a
                    x.relation = (inverse_mapping if inverse else mapping)[r.relationship_id]
                    res.append(x)
                    remaining.append(x)

        # there's one more source of relatedness, a draft can have been published
        aliases = DraftLikeDocAlias.objects.filter(document=a.document).exclude(pk__in=[x.pk for x in res])
        for oa in aliases:
            rel = None
            if a.name.startswith("rfc") and oa.name.startswith("draft"):
                rel = "that was published as"
            elif a.name.startswith("draft") and oa.name.startswith("rfc"):
                rel = "which came from"

            if rel:
                oa.related = a
                oa.relation = rel
                res.append(oa)
                remaining.append(oa)

    return res

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    related_docs = related_docsREDESIGN
