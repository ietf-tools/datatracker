# generation of mails 

import re


from django.utils.html import strip_tags
from django.utils.text import wrap
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.mail import send_mail, send_mail_text
from ietf.mailtrigger.utils import gather_address_lists

def email_admin_re_charter(request, group, subject, text, mailtrigger):
    (to,cc) = gather_address_lists(mailtrigger,group=group)
    full_subject = u"Regarding %s %s: %s" % (group.type.name, group.acronym, subject)
    text = strip_tags(text)

    send_mail(request, to, None, full_subject,
              "group/email_iesg_secretary_re_charter.txt",
              dict(text=text,
                   group=group,
                   group_url=settings.IDTRACKER_BASE_URL + group.about_url(),
                   charter_url=settings.IDTRACKER_BASE_URL + urlreverse('doc_view', kwargs=dict(name=group.charter.name)) if group.charter else "[no charter]",
                   ),
              cc=cc,
             )

def email_personnel_change(request, group, text, changed_personnel):
    (to, cc) = gather_address_lists('group_personnel_change',group=group,changed_personnel=changed_personnel)
    full_subject = u"Personnel change for %s working group" % (group.acronym)
    send_mail_text(request, to, None, full_subject, text, cc=cc)


def email_milestones_changed(request, group, changes):
    def wrap_up_email(addrs, text):

        subject = u"Milestones changed for %s %s" % (group.acronym, group.type.name)
        if re.search("Added .* for review, due",text):
            subject = u"Review Required - " + subject

        text = wrap(strip_tags(text), 70)
        text += "\n\n"
        text += u"URL: %s" % (settings.IDTRACKER_BASE_URL + group.about_url())

        send_mail_text(request, addrs.to, None, subject, text, cc=addrs.cc)

    # first send to those who should see any edits (such as management and chairs)
    addrs = gather_address_lists('group_milestones_edited',group=group)
    if addrs.to or addrs.cc:
        wrap_up_email(addrs, u"\n\n".join(c + "." for c in changes))

    # then send only the approved milestones to those who shouldn't be 
    # bothered with milestones pending approval 
    review_re = re.compile("Added .* for review, due")
    addrs = gather_address_lists('group_approved_milestones_edited',group=group)
    msg = u"\n\n".join(c + "." for c in changes if not review_re.match(c))
    if (addrs.to or addrs.cc) and msg:
        wrap_up_email(addrs, msg)

