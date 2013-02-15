from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string

from ietf.message.models import Message, SendQueue
from ietf.announcements.send_scheduled import send_scheduled_announcement
from ietf.doc.models import DocumentAuthor
from ietf.person.models import Person
from ietf.secr.utils.document import get_start_date

import datetime
import glob
import os
import time

def announcement_from_form(data, **kwargs):
    '''
    This function creates a new message record.  Taking as input EmailForm.data
    and key word arguments used to override some of the message fields
    '''
    # possible overrides
    by = kwargs.get('by',Person.objects.get(name='(System)'))
    from_val = kwargs.get('from_val','ID Tracker <internet-drafts-reply@ietf.org>')
    content_type = kwargs.get('content_type','')
    
    # from the form
    subject = data['subject']
    to_val = data['to']
    cc_val = data['cc']
    body = data['body']
    
    message = Message.objects.create(by=by,
                                     subject=subject,
                                     frm=from_val,
                                     to=to_val,
                                     cc=cc_val,
                                     body=body,
                                     content_type=content_type)
    
    # create SendQueue
    send_queue = SendQueue.objects.create(by=by,message=message)
    
    # uncomment for testing
    send_scheduled_announcement(send_queue)
    
    return message
    
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
    authors = DocumentAuthor.objects.filter(document=draft)
    
    if authors:
        prefix, first, middle, last, suffix = authors[0].author.person.name_parts()
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
    # from legacy
    if not draft.get_state('draft-iesg'):
        return ''
    
    emails = []
    if draft.notify:
        emails.append(draft.notify)
    if draft.ad:
        emails.append(draft.ad.role_email("ad").address)

    if draft.active_ballot():
        for ad, pos in draft.active_ballot().active_ad_positions().iteritems():
            if pos and pos.pos_id == "discuss":
                emails.append(ad.role_email("ad").address)

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
    
    if draft.group.acronym != 'none':
        # add chairs
        for role in draft.group.role_set.filter(name='chair'):
            if role.email.address not in emails:
                emails[role.email.address] = '"%s"' % (role.person.name)
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
    a dictonary of the action form input data (for use with replace, update, extend).
    Returns a dictionary containing initial field values for a email notification.
    The dictionary consists of to, cc, subject, body.
    
    NOTE: for type=new we are listing all authors in the message body to match legacy app.
    It appears datatracker abbreviates the list with "et al".  Datatracker scheduled_announcement
    entries have "Action" in subject whereas this app uses "ACTION"
    """
    # assert False, (draft, type, input)
    expiration_date = (datetime.date.today() + datetime.timedelta(185)).strftime('%B %d, %Y')
    new_revision = str(int(draft.rev)+1).zfill(2)
    new_filename = draft.name + '-' + new_revision + '.txt'
    curr_filename = draft.name + '-' + draft.rev + '.txt'
    data = {}
    data['cc'] = get_fullcc_list(draft)
    data['to'] = ''
    if type == 'extend':
        context = {'doc':curr_filename,'expire_date':input['expiration_date']}
        data['subject'] = 'Extension of Expiration Date for %s' % (curr_filename)
        data['body'] = render_to_string('drafts/message_extend.txt', context)

    elif type == 'new':
        # if the ID belongs to a group other than "none" add line to message body
        if draft.group.type.slug == 'wg':
            wg_message = 'This draft is a work item of the %s Working Group of the IETF.' % draft.group.name
        else:
            wg_message = ''
        context = {'wg_message':wg_message,
                   'draft':draft,
                   'authors':get_abbr_authors(draft),
                   'revision_date':draft.latest_event(type='new_revision').time.date(),
                   'timestamp':time.strftime("%Y-%m-%d%H%M%S", time.localtime())}
        data['to'] = 'i-d-announce@ietf.org'
        data['cc'] = draft.group.list_email
        data['subject'] = 'I-D ACTION:%s' % (curr_filename)
        data['body'] = render_to_string('drafts/message_new.txt', context)

    elif type == 'replace':
        '''
        input['replaced'] is a DocAlias
        input['replaced_by'] is a Document
        '''
        context = {'doc':input['replaced'].name,'replaced_by':input['replaced_by'].name}
        data['subject'] = 'Replacement of %s with %s' % (input['replaced'].name,input['replaced_by'].name)
        data['body'] = render_to_string('drafts/message_replace.txt', context)

    elif type == 'resurrect':
        last_revision = get_last_revision(draft.name)
        last_filename = draft.name + '-' + last_revision + '.txt'
        context = {'doc':last_filename,'expire_date':expiration_date}
        data['subject'] = 'Resurrection of %s' % (last_filename)
        data['body'] = render_to_string('drafts/message_resurrect.txt', context)

    elif type == 'revision':
        context = {'rev':new_revision,'doc':new_filename,'doc_base':new_filename[:-4]}
        data['to'] = get_revision_emails(draft)
        data['cc'] = ''
        data['subject'] = 'New Version Notification - %s' % (new_filename)
        data['body'] = render_to_string('drafts/message_revision.txt', context)

    elif type == 'update':
        context = {'doc':input['filename'],'expire_date':expiration_date}
        data['subject'] = 'Posting of %s' % (input['filename'])
        data['body'] = render_to_string('drafts/message_update.txt', context)

    elif type == 'withdraw':
        context = {'doc':curr_filename,'by':input['type']}
        data['subject'] = 'Withdrawl of %s' % (curr_filename)
        data['body'] = render_to_string('drafts/message_withdraw.txt', context)

    return data
