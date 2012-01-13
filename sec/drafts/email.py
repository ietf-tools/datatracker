from sec.utils.ams_utils import get_start_date
from django.core.exceptions import ObjectDoesNotExist

from django.conf import settings


import datetime
import glob
import os
import time

def announcement_from_form(data, **kwargs):
    '''
    This function creates a new scheduled_announcements record.  Taking as input EmailForm.data
    and key word arguments used to override some of the scheduled_announcement fields
    '''
    # possible overrides
    scheduled_by = kwargs.get('scheduled_by','IETFDEV')
    from_val = kwargs.get('from_val','ID Tracker <internet-drafts-reply@ietf.org>')
    content_type = kwargs.get('content_type','')
    
    # from the form
    subject = data['subject']
    to_val = data['to']
    cc_val = data['cc']
    body = data['body']
    
    """
    sa = ScheduledAnnouncement(scheduled_by=scheduled_by,
                               scheduled_date=datetime.date.today().isoformat(),
                               scheduled_time=time.strftime('%H:%M:%S'),
                               subject=subject,
                               to_val=to_val,
                               cc_val=cc_val,
                               from_val=from_val,
                               body=body,
                               first_q=1,
                               content_type=content_type)
    sa.save()
    return sa
    """
    pass
    
def get_authors(draft):
    """
    Takes a draft object and returns a list of authors suitable for a tombstone document
    """
    authors = []
    for a in draft.authors.all():
        initial = ''
        prefix, first, middle, last, suffix = a.person.name_parts()
        if first:
            initial = first + '. '
        entry = '%s%s <%s>' % (initial,last,a.address)
        authors.append(entry)
    return authors

def get_abbr_authors(draft):
    """
    Takes a draft object and returns a string of first author followed by "et al"
    for use in New Revision email body.
    """
    initial = ''
    result = ''
    authors = draft.authors.all()
    
    if authors:
        prefix, first, middle, last, suffix = authors[0].person.name_parts()
        if first:
            initial = first[0] + '. '
        result = '%s%s' % (initial,last)
        if len(authors) > 1:
            result += ', et al'
    
    return result
    
def get_authors_email(draft):
    """
    Takes a draft object and returns a string of authors suitable for an email to or cc field
    """
    authors = []
    for a in draft.authors.all():
        initial = ''
        if a.person.first_name:
            initial = a.person.first_name[0] + '. '
        entry = '%s%s <%s>' % (initial,a.person.last_name,a.person.email())
        authors.append(entry)
    return ', '.join(authors)

def get_last_revision(filename):
    """
    This function takes a filename, in the same form it appears in the InternetDraft record,
    no revision or extension (ie. draft-ietf-alto-reqs) and returns a string which is the 
    reivision number of the last active version of the document, the highest revision 
    txt document in the archive directory.  If no matching file is found raise exception.
    """
    files = glob.glob(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR,filename) + '-??.txt')
    if files:
        sorted_files = sorted(files)
        return get_revision(sorted_files[-1])
    else:
        raise Exception('last revision not found in archive')

def get_revision(name):
    """
    Takes a draft filename and returns the revision, as a string.
    """
    #return name[-6:-4]
    base,ext = os.path.splitext(name)
    return base[-2:]

def get_revision_emails(draft):
    """
    Dervied from the ColdFusion legacy app, we accumulate To: emails for a new
    revision by adding:
    1) the conents of id_internal.state_change_notice_to, this appears to be largely
    custom mail lists for the document or group
    2) the main AD, via id_internal.job_owner
    3) any ad who has marked "discuss" in the ballot associated with this id_internal
    """
    emails = []
    # from legacy
    if not draft.get_state('draft-iesg'):
        return ''
        
    # get state_change_notice_to
    emails.append(draft.notify)
    
    # get job_owner
    emails.append(draft.ad.email_address())
    
    # TODO
    # get ballots discuss
    # need to catch errors here because in some cases the referenced ballot_info
    # record does not exist
    #try:
    #    position_list = id.ballot.positions.filter(discuss=1)
    #    for p in position_list:
    #        emails.append(p.ad.person.email())
    #except ObjectDoesNotExist:
    #    pass

    return ', '.join(emails)

def add_email(emails,person):
    if person.email() not in emails:
        emails[person.email()] = '"%s %s"' % (person.first_name,person.last_name)

def get_fullcc_list(draft):
    """
    This function takes a draft object and returns a string of emails to use in cc field
    of a standard notification.  Uses an intermediate "emails" dictionary, emails are the
    key, name is the value, to prevent adding duplicate emails to the list.
    """
    emails = {}
    # get authors
    for author in draft.authors.all():
        if author.address not in emails:
            emails[author.address] = '"%s"' % (author.person.name)
    # add chairs
    if draft.group.pk != 1027:
        for chair in draft.group.role_set.filter(name='chair'):
            if author.address not in emails:
                emails[chair.address] = '"%s"' % (chair.person.name)
    # add AD
    if draft.group.type.slug == 'wg':    
        emails['%s-ads@tools.ietf.org' % draft.group.acronym] = '"%s-ads"' % (draft.group.acronym)
    elif draft.group.type.slug == 'rg':
        email = draft.group.parent.role_set.filter(name='chair')[0].email
        emails[email.address] = '"%s"' % (email.person.name)
    # add sheperd
    if draft.shepherd:
        emails[draft.shepherd.email_address()] = '"%s"' % (draft.shepherd.name)
    
    """    
    # add wg advisor
    try:
        advisor = IETFWG.objects.get(group_acronym=draft.group.acronym_id).area_director
        if advisor:
            add_email(emails,advisor.person)
    except ObjectDoesNotExist:
        pass
    # add shepherding ad
    try:
        id = IDInternal.objects.get(draft=draft.id_document_tag)
        add_email(emails,id.job_owner.person)
    except ObjectDoesNotExist:
        pass 
    # add state_change_notice to
    try:
        id = IDInternal.objects.get(draft=draft.id_document_tag)
        for email in id.state_change_notice_to.split(','):
            if email.strip() not in emails:
                emails[email.strip()] = ''
    except ObjectDoesNotExist:
        pass 
    """
    
    # use sort so we get consistently ordered lists
    result_list = []
    for key in sorted(emails):
        if emails[key]:
            result_list.append('%s <%s>' % (emails[key],key))
        else:
            result_list.append('<%s>' % key)

    return ','.join(result_list) 

def get_email_initial(draft, type=None, input=None):
    """
    Takes a draft object, a string representing the email type:
    (extend,new,replace,resurrect,revision,update,withdraw) and
    a dictonary of the action form input data (for use with replace, update).
    Returns a dictionary containing initial field values for a email notification.
    The dictionary consists of to, cc, subject, body.
    
    NOTE: for type=new we are listing all authors in the message body to match legacy app.
    It appears datatracker abbreviates the list with "et al".  Datatracker scheduled_announcement
    entries have "Action" in subject whereas this app uses "ACTION"
    """
    # assert False, (draft, type, input)
    expiration_date = datetime.date.today() + datetime.timedelta(185)
    new_revision = str(int(draft.rev)+1).zfill(2)
    new_filename = draft.name + '-' + new_revision + '.txt'
    curr_filename = draft.name + '-' + draft.rev + '.txt'
    data = {}
    data['cc'] = get_fullcc_list(draft)
    data['to'] = ''
    if type == 'extend':
        data['subject'] = 'Extension of Expiration Date for %s' % (curr_filename)
        data['body'] = """As you requested, the expiration date for
%s has been extended.  The draft
will expire on %s unless it is replaced by an updated version, or the 
Secretariat has been notified that the document is under official review by the
IESG or has been passed to the IRSG or RFC Editor for review and/or publication
as an RFC.

IETF Secretariat.""" %(curr_filename, expiration_date.strftime('%B %d, %Y'))

    elif type == 'new':
        # from emailannouncement.cfm
        # if the ID belongs to a group other than "none" add line to message body
        if draft.group.type.slug == 'wg':
            wg_message = 'This draft is a work item of the %s Working Group of the IETF.' % draft.group.name
        else:
            wg_message = ''
        data['to'] = 'i-d-announce@ietf.org'
        data['cc'] = draft.group.list_email
        data['subject'] = 'I-D ACTION:%s' % (curr_filename)
        data['body'] = """--NextPart

A new Internet-Draft is available from the on-line Internet-Drafts directories.
%s

    Title         : %s
    Author(s)     : %s
    Filename      : %s
    Pages         : %s
    Date          : %s
    
%s

A URL for this Internet-Draft is:
http://www.ietf.org/internet-drafts/%s

Internet-Drafts are also available by anonymous FTP at:
ftp://ftp.ietf.org/internet-drafts/

Below is the data which will enable a MIME compliant mail reader
implementation to automatically retrieve the ASCII version of the
Internet-Draft.

--NextPart
Content-Type: Message/External-body;
    name="%s";
    site="ftp.ietf.org";
    access-type="anon-ftp";
    directory="internet-drafts"

Content-Type: text/plain
Content-ID:     <%s.I-D@ietf.org>

--NextPart--
""" % (wg_message,
       draft.title,
       get_abbr_authors(draft),
       draft.name,
       draft.pages,
       get_start_date(draft),
       draft.abstract,
       draft.name,
       draft.name,
       time.strftime("%Y-%m-%d%H%M%S", time.localtime()))

    elif type == 'replace':
        data['subject'] = 'Replacement of %s with %s' % (curr_filename,input['replaced_by'])
        data['body'] = """As you requested, %s has been marked as replaced by 
%s in the IETF Internet-Drafts database.

IETF Secretariat.""" % (curr_filename,input['replaced_by'])

    elif type == 'resurrect':
        last_revision = get_last_revision(draft.name)
        last_filename = draft.name + '-' + last_revision + '.txt'
        data['subject'] = 'Resurrection of %s' % (last_filename)
        data['body'] = """As you requested, %s has been resurrected.  The draft will expire on
%s unless it is replaced by an updated version, or the Secretariat has been notified that the
document is under official review by the IESG or has been passed to the IRSG or RFC Editor for review and/or
publication as an RFC.

IETF Secretariat.""" % (last_filename, expiration_date.strftime('%B %d, %Y'))

    elif type == 'revision':
        data['to'] = get_revision_emails(draft)
        data['cc'] = ''
        data['subject'] = 'New Version Notification - %s' % (new_filename)
        data['body'] = """New version (-%s) has been submitted for %s.
http://www.ietf.org/internet-drafts/%s

Diff from previous version:
http://tools.ietf.org/rfcdiff?url2=%s

IETF Secretariat.""" % (new_revision, new_filename, new_filename, new_filename[:-4])

    elif type == 'update':
        data['subject'] = 'Posting of %s' % (input['filename'])
        data['body'] = """As you requested, %s an updated 
version of an expired Internet-Draft, has been posted.  The draft will expire 
on %s unless it is replaced by an updated version, or the 
Secretariat has been notified that the document is under official review by the
IESG or has been passed to the IRSG or RFC Editor for review and/or publication
as an RFC.

IETF Secretariat.""" % (input['filename'], expiration_date.strftime('%B %d, %Y'))

    elif type == 'withdraw':
        data['subject'] = 'Withdrawl of %s' % (curr_filename)
        data['body'] = """As you requested, %s 
has been marked as withdrawn by the IETF in the IETF Internet-Drafts database.

IETF Secretariat.""" % (curr_filename)

    return data
