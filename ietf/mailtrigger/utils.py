# Copyright The IETF Trust 2015-2019, All Rights Reserved

from collections import namedtuple

import debug                            # pyflakes:ignore

from ietf.mailtrigger.models import MailTrigger, Recipient
from ietf.submit.models import Submission
from ietf.utils.mail import excludeaddrs

class AddrLists(namedtuple('AddrLists',['to','cc'])):

    __slots__ = ()

    def as_strings(self,compact=True):

        separator = ", " if compact else ",\n    "
        to_string = separator.join(self.to)
        cc_string = separator.join(self.cc)

        return namedtuple('AddrListsAsStrings',['to','cc'])(to=to_string,cc=cc_string)


def gather_address_lists(slug, skipped_recipients=None, create_from_slug_if_not_exists=None, 
                         desc_if_not_exists=None, **kwargs):
    mailtrigger = get_mailtrigger(slug, create_from_slug_if_not_exists, desc_if_not_exists)

    to = set()
    for recipient in mailtrigger.to.all():
        to.update(recipient.gather(**kwargs))
    to.discard('')
    if skipped_recipients:
        to = excludeaddrs(to, skipped_recipients)

    cc = set()
    for recipient in mailtrigger.cc.all():
        cc.update(recipient.gather(**kwargs))
    cc.discard('')
    if skipped_recipients:
        cc = excludeaddrs(cc, skipped_recipients)

    return AddrLists(to=sorted(list(to)),cc=sorted(list(cc)))

def get_mailtrigger(slug, create_from_slug_if_not_exists, desc_if_not_exists):
    try:
        mailtrigger = MailTrigger.objects.get(slug=slug)
    except MailTrigger.DoesNotExist:
        if create_from_slug_if_not_exists and desc_if_not_exists:
            template = MailTrigger.objects.get(slug=create_from_slug_if_not_exists)
            mailtrigger = MailTrigger.objects.create(slug=slug, desc=desc_if_not_exists)
            mailtrigger.to.set(template.to.all())
            mailtrigger.cc.set(template.cc.all())
            if slug.startswith('review_completed') and slug.endswith('early'):
                mailtrigger.cc.remove('ietf_last_call')
        else:
            raise
    return mailtrigger


def gather_relevant_expansions(**kwargs):

    def starts_with(prefix):
        return MailTrigger.objects.filter(slug__startswith=prefix).values_list('slug',flat=True)

    relevant = set() 
    
    if 'doc' in kwargs:

        doc = kwargs['doc']

        # PEY: does this need to include irsg_ballot_saved as well?
        relevant.update(['doc_state_edited','doc_telechat_details_changed','ballot_deferred','iesg_ballot_saved'])

        if doc.type_id in ['draft','statchg']:
            relevant.update(starts_with('last_call_'))

        if doc.type_id == 'draft':
            relevant.update(starts_with('doc_'))
            relevant.update(starts_with('resurrection_'))
            relevant.update(['ipr_posted_on_doc',])
            if doc.stream_id == 'ietf':
                relevant.update(['ballot_approved_ietf_stream','pubreq_iesg'])
            else:
                relevant.update(['pubreq_rfced'])
            last_submission = Submission.objects.filter(name=doc.name,state='posted').order_by('-rev').first()
            if last_submission and 'submission' not in kwargs:
                kwargs['submission'] = last_submission

        if  doc.type_id == 'conflrev':
            relevant.update(['conflrev_requested','ballot_approved_conflrev'])
        if  doc.type_id == 'charter':
            relevant.update(['charter_external_review','ballot_approved_charter'])

    if 'group' in kwargs:

        relevant.update(starts_with('group_'))
        relevant.update(starts_with('milestones_'))
        group = kwargs['group']       
        if group.features.acts_like_wg:
            relevant.update(starts_with('session_'))
        if group.features.has_chartering_process:
            relevant.update(['charter_external_review',])

    if 'submission' in kwargs:

        relevant.update(starts_with('sub_'))

    rule_list = []
    for mailtrigger in MailTrigger.objects.filter(slug__in=relevant):
        addrs = gather_address_lists(mailtrigger.slug,**kwargs)
        if addrs.to or addrs.cc:
            rule_list.append((mailtrigger.slug,mailtrigger.desc,addrs.to,addrs.cc))
    return sorted(rule_list)

def get_base_submission_message_address():
    return Recipient.objects.get(slug='submission_manualpost_handling').gather()[0]

def get_base_ipr_request_address():
    return Recipient.objects.get(slug='ipr_requests').gather()[0]


