from collections import namedtuple
from ietf.mailtoken.models import MailToken, Recipient

class AddrLists(namedtuple('AddrLists',['to','cc'])):

    __slots__ = ()

    def as_strings(self,compact=True):

        separator = ", " if compact else ",\n    "
        to_string = separator.join(self.to)
        cc_string = separator.join(self.cc)

        return namedtuple('AddrListsAsStrings',['to','cc'])(to=to_string,cc=cc_string)

def gather_address_lists(slug, **kwargs):
    mailtoken = MailToken.objects.get(slug=slug)

    to = set()
    for recipient in mailtoken.to.all():
        to.update(recipient.gather(**kwargs))
    to.discard('')

    cc = set()
    for recipient in mailtoken.cc.all():
        cc.update(recipient.gather(**kwargs))
    cc.discard('')

    return AddrLists(to=list(to),cc=list(cc))

def gather_relevant_expansions(**kwargs):
    relevant = set() 
    
    if 'doc' in kwargs:

        doc = kwargs['doc']

        relevant.update(MailToken.objects.filter(slug__startswith='doc_').values_list('slug',flat=True))

        if doc.stream_id == 'ietf':
            relevant.update(['ballot_approved_ietf_stream'])
        else:
            relevant.update(['pubreq_rfced'])

        if doc.type_id in ['draft','statchg']:
            relevant.update(MailToken.objects.filter(slug__startswith='last_call_').values_list('slug',flat=True))
        if doc.type_id == 'draft':
            relevant.update(['ipr_posted_on_doc',])
        if  doc.type_id == 'conflrev':
            relevant.update(['conflrev_requested','ballot_approved_conflrev'])
        if  doc.type_id == 'charter':
            relevant.update(['charter_external_review','ballot_approved_charter'])

    rule_list = []
    for mailtoken in MailToken.objects.filter(slug__in=relevant):
        addrs = gather_address_lists(mailtoken.slug,**kwargs)
        rule_list.append((mailtoken.slug,mailtoken.desc,addrs.to,addrs.cc))
    return sorted(rule_list)

#def gather_relevant_expansions_recipient(**kwargs):
#    relevant_tokens = []
#
#    if 'doc' in kwargs:
#        relevant_tokens.extend(Recipient.objects.filter(slug__startswith='doc').values_list('slug',flat=True))
#
#    rule_dict = {}
#
#    for recipient in Recipient.objects.filter(slug__in=relevant_tokens):
#    #for recipient in Recipient.objects.all():
#        addrs = recipient.gather(**kwargs)
#        if addrs:
#            rule_dict[recipient.slug] = recipient.gather(**kwargs)
#    return sorted(rule_dict.iteritems())

def get_base_ipr_request_address():
    return Recipient.objects.get(slug='ipr_requests').gather()[0]


