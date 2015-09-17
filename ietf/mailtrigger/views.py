# Copyright The IETF Trust 2015, All Rights Reserved

from inspect import getsourcelines

from django.shortcuts import render, get_object_or_404

from ietf.mailtrigger.models import MailTrigger, Recipient

def show_triggers(request, mailtrigger_slug=None):
    mailtriggers = MailTrigger.objects.all()
    if mailtrigger_slug:
        get_object_or_404(MailTrigger,slug=mailtrigger_slug)
        mailtriggers = mailtriggers.filter(slug=mailtrigger_slug) 
    return render(request,'mailtrigger/trigger.html',{'mailtrigger_slug':mailtrigger_slug,
                                                    'mailtriggers':mailtriggers})
def show_recipients(request, recipient_slug=None):
    recipients = Recipient.objects.all()
    if recipient_slug:
        get_object_or_404(Recipient,slug=recipient_slug)
        recipients = recipients.filter(slug=recipient_slug)
    for recipient in recipients:
        fname = 'gather_%s'%recipient.slug
        if hasattr(recipient,fname):
            recipient.code = ''.join(getsourcelines(getattr(recipient,fname))[0])
    return render(request,'mailtrigger/recipient.html',{'recipient_slug':recipient_slug,
                                                      'recipients':recipients})
