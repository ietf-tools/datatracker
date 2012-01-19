def get_rfc_num(doc):
    qs = doc.docalias_set.filter(name__startswith='rfc')
    return qs[0].name[3:] if qs else None

def is_draft(doc):
    if doc.docalias_set.filter(name__startswith='rfc'):
        return False
    else:
        return True