# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import debug                            # pyflakes:ignore

def get_genitive(name):
    """Return the genitive form of name"""
    return name + "'" if name.endswith('s') else name + "'s"

def get_ipr_summary(disclosure):
    """Return IPR related document names as a formatted string"""
    names = []
    for doc in disclosure.docs.all():
        if doc.name.startswith('rfc'):
            names.append('RFC {}'.format(doc.name[3:]))
        else:
            names.append(doc.name)
    
    if disclosure.other_designations:
        names.append(disclosure.other_designations)

    if not names:
        summary = ''
    elif len(names) == 1:
        summary = names[0]
    elif len(names) == 2:
        summary = " and ".join(names)
    elif len(names) > 2:
        summary = ", ".join(names[:-1]) + ", and " + names[-1]
    return summary if len(summary) <= 128 else summary[:125]+'...'


def iprs_from_docs(aliases,**kwargs):
    """Returns a list of IPRs related to doc aliases"""
    iprdocrels = []
    for alias in aliases:
        for document in alias.docs.all():
            if document.ipr(**kwargs):
                iprdocrels += document.ipr(**kwargs)
    return list(set([i.disclosure for i in iprdocrels]))
    
def related_docs(alias, relationship=('replaces', 'obs')):
    """Returns list of related documents"""

    results = []
    for doc in alias.docs.all():
        results += list(doc.docalias.all())
    
    rels = []
    for doc in alias.docs.all():
        rels += list(doc.all_relations_that_doc(relationship))

    for rel in rels:
        rel_aliases = list(rel.target.document.docalias.all())
        
        for x in rel_aliases:
            x.related = rel
            x.relation = rel.relationship.revname
        results += rel_aliases

    return list(set(results))

    
