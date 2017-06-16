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

    if len(names) == 1:
        return names[0]
    elif len(names) == 2:
        return " and ".join(names)
    elif len(names) > 2:
        return ", ".join(names[:-1]) + ", and " + names[-1]

def iprs_from_docs(aliases,**kwargs):
    """Returns a list of IPRs related to doc aliases"""
    iprdocrels = []
    for alias in aliases:
        if alias.document.ipr(**kwargs):
            iprdocrels += alias.document.ipr(**kwargs)
    return list(set([i.disclosure for i in iprdocrels]))
    
def related_docs(alias):
    """Returns list of related documents"""
    results = list(alias.document.docalias_set.all())
    
    rels = alias.document.all_relations_that_doc(['replaces','obs'])

    for rel in rels:
        rel_aliases = list(rel.target.document.docalias_set.all())
        
        for x in rel_aliases:
            x.related = rel
            x.relation = rel.relationship.revname
        results += rel_aliases
    return list(set(results))