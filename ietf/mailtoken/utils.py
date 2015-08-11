
from django.core.exceptions import ObjectDoesNotExist

from ietf.mailtoken.models import MailToken

def gather_address_list(slug,**kwargs):
    
    addrs = []

    try:
       mailtoken = MailToken.objects.get(slug=slug)
    except ObjectDoesNotExist:
       # TODO remove the raise here, or find a better way to detect runtime misconfiguration
       raise
       return addrs

    for recipient in mailtoken.recipients.all():
        addrs.extend(recipient.gather(**kwargs))

    return list(set(addrs))

def gather_addresses(slug,**kwargs):
    return ",\n   ".join(gather_address_list(slug,**kwargs))
