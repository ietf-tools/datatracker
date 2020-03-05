# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-
# generation of mails 


import re


from django.utils.html import strip_tags
from django.conf import settings
from django.urls import reverse as urlreverse

from ietf.utils.mail import send_mail, send_mail_text
from ietf.utils.text import wordwrap
from ietf.mailtrigger.utils import gather_address_lists

def email_admin_re_charter(request, group, subject, text, mailtrigger):
    (to,cc) = gather_address_lists(mailtrigger,group=group)
    full_subject = "Regarding %s %s: %s" % (group.type.name, group.acronym, subject)
    text = strip_tags(text)

    send_mail(request, to, None, full_subject,
              "group/email_iesg_secretary_re_charter.txt",
              dict(text=text,
                   group=group,
                   group_url=settings.IDTRACKER_BASE_URL + group.about_url(),
                   charter_url=settings.IDTRACKER_BASE_URL + urlreverse('ietf.doc.views_doc.document_main', kwargs=dict(name=group.charter.name)) if group.charter else "[no charter]",
                   ),
              cc=cc,
             )

def email_personnel_change(request, group, text, changed_personnel):
    (to, cc) = gather_address_lists('group_personnel_change',group=group,changed_personnel=changed_personnel)
    full_subject = "Personnel change for %s %s" % (group.acronym,group.type.name)
    send_mail_text(request, to, None, full_subject, text, cc=cc)


def email_milestones_changed(request, group, changes, states):
    def wrap_up_email(addrs, text):

        subject = "Milestones changed for %s %s" % (group.acronym, group.type.name)
        if re.search("Added .* for review, due",text):
            subject = "Review Required - " + subject

        text = wordwrap(strip_tags(text), 78)
        text += "\n\n"
        text += "URL: %s" % (settings.IDTRACKER_BASE_URL + group.about_url())

        send_mail_text(request, addrs.to, None, subject, text, cc=addrs.cc)

    # first send to those who should see any edits (such as management and chairs)
    addrs = gather_address_lists('group_milestones_edited',group=group)
    if addrs.to or addrs.cc:
        wrap_up_email(addrs, "\n\n".join(c + "." for c in changes))

    # then send only the approved milestones to those who shouldn't be 
    # bothered with milestones pending approval 
    addrs = gather_address_lists('group_approved_milestones_edited',group=group)
    msg = "\n\n".join(c + "." for c,s in zip(changes,states) if not s == "review")
    if (addrs.to or addrs.cc) and msg:
        wrap_up_email(addrs, msg)

def email_comment(request, event):
    (to, cc) = gather_address_lists('group_added_comment',group=event.group)
    send_mail(request, to, None, "Comment added to %s history"%event.group.acronym,
              "group/comment_added_email.txt",
              dict( event = event, 
                    group_url=settings.IDTRACKER_BASE_URL + event.group.about_url(),
              ),
              cc = cc)
                    
