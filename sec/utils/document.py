def get_full_path(doc):
    '''
    Returns for name of file on disk with full path.  This should really be a method on doc
    NOTE: this currently only works for material file types
    '''
    import os
    
    if doc.type_id not in ('slides','agenda','minutes') or not doc.external_url:
        return None
    return os.path.join(doc.get_file_path(), doc.external_url)
    
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