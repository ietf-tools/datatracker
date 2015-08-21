# Copyright The IETF Trust 2015, All Rights Reserved

from inspect import getsourcelines

from django.shortcuts import render, get_object_or_404

from ietf.mailtoken.models import MailToken, Recipient

def show_tokens(request, mailtoken_slug=None):
    mailtokens = MailToken.objects.all()
    if mailtoken_slug:
        get_object_or_404(MailToken,slug=mailtoken_slug)
        mailtokens = mailtokens.filter(slug=mailtoken_slug) 
    return render(request,'mailtoken/token.html',{'mailtoken_slug':mailtoken_slug,
                                                  'mailtokens':mailtokens})
def show_recipients(request, recipient_slug=None):
    recipients = Recipient.objects.all()
    if recipient_slug:
        get_object_or_404(Recipient,slug=recipient_slug)
        recipients = recipients.filter(slug=recipient_slug)
    for recipient in recipients:
        fname = 'gather_%s'%recipient.slug
        if hasattr(recipient,fname):
            recipient.code = ''.join(getsourcelines(getattr(recipient,fname))[0])
    return render(request,'mailtoken/recipient.html',{'recipient_slug':recipient_slug,
                                                      'recipients':recipients})
