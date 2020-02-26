# Copyright The IETF Trust 2013-2020, All Rights Reserved
import datetime
import glob
import os

import debug           # pyflakes:ignore

from django.conf import settings
from django.template.loader import render_to_string

from ietf.message.models import Message, SendQueue
from ietf.message.utils import send_scheduled_message_from_send_queue
from ietf.doc.models import DocumentAuthor
from ietf.person.models import Person

def announcement_from_form(data, **kwargs):
    '''
    This function creates a new message record.  Taking as input EmailForm.data
    and key word arguments used to override some of the message fields
    '''
    # possible overrides
    by = kwargs.get('by',Person.objects.get(name='(System)'))
    from_val = kwargs.get('from_val','Datatracker <internet-drafts-reply@ietf.org>')
    content_type = kwargs.get('content_type','text/plain')
    
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
    send_scheduled_message_from_send_queue(send_queue)
    
    return message
    
def get_authors(draft):
    """
    Takes a draft object and returns a list of authors suitable for a tombstone document
    """
    authors = []
    for a in draft.documentauthor_set.all():
        initial = ''
        prefix, first, middle, last, suffix = a.person.name_parts()
        if first:
            initial = first + '. '
        entry = '%s%s <%s>' % (initial,last,a.email.address)
        authors.append(entry)
    return authors

def get_abbr_authors(draft):
    """
    Takes a draft object and returns a string of first author followed by "et al"
    for use in New Revision email body.
    """
    initial = ''
    result = ''
    authors = DocumentAuthor.objects.filter(document=draft).order_by("order")
    
    if authors:
        prefix, first, middle, last, suffix = authors[0].person.name_parts()
        if first:
            initial = first[0] + '. '
        result = '%s%s' % (initial,last)
        if len(authors) > 1:
            result += ', et al'
    
    return result
    
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

def get_fullcc_list(draft):
    """
    This function takes a draft object and returns a string of emails to use in cc field
    of a standard notification.  Uses an intermediate "emails" dictionary, emails are the
    key, name is the value, to prevent adding duplicate emails to the list.
    """
    emails = {}
    # get authors
    for author in draft.documentauthor_set.all():
        if author.email and author.email.address not in emails:
            emails[author.email.address] = '"%s"' % (author.person.name)
    
    if draft.group.acronym != 'none':
        # add chairs
        for role in draft.group.role_set.filter(name='chair'):
            if role.email.address not in emails:
                emails[role.email.address] = '"%s"' % (role.person.name)
        # add AD
        if draft.group.type.slug == 'wg':    
            emails['%s-ads@ietf.org' % draft.group.acronym] = '"%s-ads"' % (draft.group.acronym)
        elif draft.group.type.slug == 'rg':
            email = draft.group.parent.role_set.filter(name='chair')[0].email
            emails[email.address] = '"%s"' % (email.person.name)
    
    # add sheperd
    if draft.shepherd:
        emails[draft.shepherd.address] = '"%s"' % (draft.shepherd.person.name)
    
    # use sort so we get consistently ordered lists
    result_list = []
    for key in sorted(emails):
        if emails[key]:
            result_list.append('%s <%s>' % (emails[key],key))
        else:
            result_list.append('<%s>' % key)

    return ','.join(result_list) 

def get_email_initial(draft, action=None, input=None):
    """
    Takes a draft object, a string representing the email type:
    (extend,resurrect,revision,update,withdraw) and
    a dictonary of the action form input data (for use with update, extend).
    Returns a dictionary containing initial field values for a email notification.
    The dictionary consists of to, cc, subject, body.
    
    """
    expiration_date = (datetime.date.today() + datetime.timedelta(185)).strftime('%B %d, %Y')
    curr_filename = draft.name + '-' + draft.rev + '.txt'
    data = {}
    data['cc'] = get_fullcc_list(draft)
    data['to'] = ''
    data['action'] = action

    if action == 'extend':
        context = {'doc':curr_filename,'expire_date':input['expiration_date']}
        data['subject'] = 'Extension of Expiration Date for %s' % (curr_filename)
        data['body'] = render_to_string('drafts/message_extend.txt', context)
        data['expiration_date'] = input['expiration_date']

    elif action == 'resurrect':
        last_revision = get_last_revision(draft.name)
        last_filename = draft.name + '-' + last_revision + '.txt'
        context = {'doc':last_filename,'expire_date':expiration_date}
        data['subject'] = 'Resurrection of %s' % (last_filename)
        data['body'] = render_to_string('drafts/message_resurrect.txt', context)
        data['action'] = action

    elif action == 'withdraw':
        context = {'doc':curr_filename,'by':input['withdraw_type']}
        data['subject'] = 'Withdraw of %s' % (curr_filename)
        data['body'] = render_to_string('drafts/message_withdraw.txt', context)
        data['action'] = action
        data['withdraw_type'] = input['withdraw_type']

    return data
