def get_ad_email_list(group):
    '''
    This function takes a group and returns the Area Director email as a list.
    NOTE: we still have custom logic here for IRTF groups, where the "Area Director"
    is the chair of the parent group, 'irtf'.
    '''
    emails = []
    if group.type.slug == 'wg':    
        emails.append('%s-ads@tools.ietf.org' % group.acronym)
    elif group.type.slug == 'rg' and group.parent:
        emails.append(group.parent.role_set.filter(name='chair')[0].email.address)
    return emails

def get_cc_list(group, person=None):
    '''
    This function takes a Group and Person.  It returns a list of emails for the ads and chairs of
    the group and the person's email if it isn't already in the list.
    
    Per Pete Resnick, at IETF 80 meeting, session request notifications
    should go to chairs,ads lists not individuals.
    '''
    emails = []
    emails.extend(get_ad_email_list(group))
    emails.extend(get_chair_email_list(group))
    if person and person.email_address() not in emails:
        emails.append(person.email_address())
    return emails
    
def get_chair_email_list(group):
    '''
    This function takes a group and returns chair email(s) as a list.
    '''
    return [ r.email.address for r in group.role_set.filter(name='chair') ]

