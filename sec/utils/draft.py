def get_rfc_num(doc):
    qs = doc.docalias_set.filter(name__startswith='rfc')
    return qs[0].name[3:] if qs else None

def is_draft(doc):
    if doc.docalias_set.filter(name__startswith='rfc'):
        return False
    else:
        return True

def get_start_date(doc):
    '''
    This function takes a document object and returns the date of the first
    new revision doc event
    '''
    # based on ietf.doc.proxy
    event = doc.docevent_set.filter(type='new_revision').order_by('time')
    return event[0].time.date() if event else None