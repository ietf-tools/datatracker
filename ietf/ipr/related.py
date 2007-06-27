# Copyright The IETF Trust 2007, All Rights Reserved

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
