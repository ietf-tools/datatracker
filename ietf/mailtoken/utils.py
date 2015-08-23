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

def get_base_ipr_request_address():
    return Recipient.objects.get(slug='ipr_requests').gather()[0]


