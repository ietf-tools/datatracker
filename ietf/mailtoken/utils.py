from ietf.mailtoken.models import MailToken, Recipient

def gather_address_list(slug,**kwargs):
    
    addrs = []

    if slug.endswith('_cc'):
        mailtoken = MailToken.objects.get(slug=slug[:-3])
        for recipient in mailtoken.cc.all():
            addrs.extend(recipient.gather(**kwargs))
    else:
        mailtoken = MailToken.objects.get(slug=slug)
        for recipient in mailtoken.to.all():
            addrs.extend(recipient.gather(**kwargs))

    return list(set([addr for addr in addrs if addr]))

def gather_addresses(slug,**kwargs):
    return ",\n   ".join(gather_address_list(slug,**kwargs))

def get_base_ipr_request_address():
    return Recipient.objects.get(slug='ipr_requests').gather()[0]


