# generation of mails 

import datetime
import re


from django.utils.html import strip_tags
from django.utils.text import wrap
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.mail import send_mail, send_mail_text
from ietf.group.models import Group
from ietf.group.utils import milestone_reviewer_for_group_type

def email_iesg_secretary_re_charter(request, group, subject, text):
    to = ["iesg-secretary@ietf.org"]
    full_subject = u"Regarding %s %s: %s" % (group.type.name, group.acronym, subject)
    text = strip_tags(text)

    send_mail(request, to, None, full_subject,
              "group/email_iesg_secretary_re_charter.txt",
              dict(text=text,
                   group=group,
                   group_url=settings.IDTRACKER_BASE_URL + group.about_url(),
                   charter_url=settings.IDTRACKER_BASE_URL + urlreverse('doc_view', kwargs=dict(name=group.charter.name)) if group.charter else "[no charter]",
                   )
              )

def email_iesg_secretary_personnel_change(request, group, text):
    to = ["iesg-secretary@ietf.org"]
    full_subject = u"Personnel change for %s working group" % (group.acronym)
    send_mail_text(request, to, None, full_subject,text)

def email_interested_parties_re_changed_delegates(request, group, title, added, deleted):

    # Send to management and chairs
    to = []
    if group.ad_role():
        to.append(group.ad_role().email.formatted_email())
    elif group.type_id == "rg":
        to.append("IRTF Chair <irtf-chair@irtf.org>")

    for r in group.role_set.filter(name="chair"):
        to.append(r.formatted_email())

    # Send to the delegates who were added or deleted
    for delegate in added:
        to.append(delegate.formatted_email())

    for delegate in deleted:
        to.append(delegate.formatted_email())

    personnel_change_text=""
    if added:
        change_text=title + ' added: ' + ", ".join(x.formatted_email() for x in added)
        personnel_change_text+=change_text+"\n"
    if deleted:
        change_text=title + ' deleted: ' + ", ".join(x.formatted_email() for x in deleted)
        personnel_change_text+=change_text+"\n"

    if to:
        full_subject = u"%s changed for %s working group" % (title, group.acronym)
        send_mail_text(request, to, None, full_subject,personnel_change_text)


def email_milestones_changed(request, group, changes):
    def wrap_up_email(to, text):

        subject = u"Milestones changed for %s %s" % (group.acronym, group.type.name)
        if re.search("Added .* for review, due",text):
            subject = u"Review Required - " + subject

        text = wrap(strip_tags(text), 70)
        text += "\n\n"
        text += u"URL: %s" % (settings.IDTRACKER_BASE_URL + group.about_url())

        send_mail_text(request, to, None, subject, text)

    # first send to management and chairs
    to = []
    if group.ad_role():
        to.append(group.ad_role().email.formatted_email())
    elif group.type_id == "rg":
        to.append("IRTF Chair <irtf-chair@irtf.org>")

    for r in group.role_set.filter(name="chair"):
        to.append(r.formatted_email())

    if to:
        wrap_up_email(to, u"\n\n".join(c + "." for c in changes))

    # then send to group
    if group.list_email:
        review_re = re.compile("Added .* for review, due")
        to = [ group.list_email ]
        msg = u"\n\n".join(c + "." for c in changes if not review_re.match(c))
        if msg:
            wrap_up_email(to, msg)


def email_milestone_review_reminder(group, grace_period=7):
    """Email reminders about milestones needing review to management."""
    to = []

    if group.ad_role():
        to.append(group.ad_role().email.formatted_email())
    elif group.type_id == "rg":
        to.append("IRTF Chair <irtf-chair@irtf.org>")

    if not to:
        return False

    cc = [r.formatted_email() for r in group.role_set.filter(name="chair")]

    now = datetime.datetime.now()
    too_early = True

    milestones = group.groupmilestone_set.filter(state="review")
    for m in milestones:
        e = m.milestonegroupevent_set.filter(type="changed_milestone").order_by("-time")[:1]
        m.days_ready = (now - e[0].time).days if e else None

        if m.days_ready == None or m.days_ready >= grace_period:
            too_early = False

    if too_early:
        return False

    subject = u"Reminder: Milestone%s needing review in %s %s" % ("s" if len(milestones) > 1 else "", group.acronym, group.type.name)

    send_mail(None, to, None,
              subject,
              "group/reminder_milestones_need_review.txt",
              dict(group=group,
                   milestones=milestones,
                   reviewer=milestone_reviewer_for_group_type(group.type_id),
                   url=settings.IDTRACKER_BASE_URL + urlreverse("group_edit_milestones", kwargs=dict(group_type=group.type_id, acronym=group.acronym)),
                   cc=cc,
               )
             )

    return True

def groups_with_milestones_needing_review():
    return Group.objects.filter(groupmilestone__state="review").distinct()

def email_milestones_due(group, early_warning_days):
    to = [r.formatted_email() for r in group.role_set.filter(name="chair")]

    today = datetime.date.today()
    early_warning = today + datetime.timedelta(days=early_warning_days)

    milestones = group.groupmilestone_set.filter(due__in=[today, early_warning],
                                                 resolved="", state="active")

    subject = u"Reminder: Milestone%s are soon due in %s %s" % ("s" if len(milestones) > 1 else "", group.acronym, group.type.name)

    send_mail(None, to, None,
              subject,
              "group/reminder_milestones_due.txt",
              dict(group=group,
                   milestones=milestones,
                   today=today,
                   early_warning_days=early_warning_days,
                   url=settings.IDTRACKER_BASE_URL + group.about_url(),
                   ))

def groups_needing_milestones_due_reminder(early_warning_days):
    """Return groups having milestones that are either
    early_warning_days from being due or are due today."""
    today = datetime.date.today()
    return Group.objects.filter(state="active", groupmilestone__due__in=[today, today + datetime.timedelta(days=early_warning_days)], groupmilestone__resolved="", groupmilestone__state="active").distinct()

def email_milestones_overdue(group):
    to = [r.formatted_email() for r in group.role_set.filter(name="chair")]

    today = datetime.date.today()

    milestones = group.groupmilestone_set.filter(due__lt=today, resolved="", state="active")
    for m in milestones:
        m.months_overdue = (today - m.due).days // 30

    subject = u"Reminder: Milestone%s overdue in %s %s" % ("s" if len(milestones) > 1 else "", group.acronym, group.type.name)

    send_mail(None, to, None,
              subject,
              "group/reminder_milestones_overdue.txt",
              dict(group=group,
                   milestones=milestones,
                   url=settings.IDTRACKER_BASE_URL + group.about_url(),
                   ))

def groups_needing_milestones_overdue_reminder(grace_period=30):
    cut_off = datetime.date.today() - datetime.timedelta(days=grace_period)
    return Group.objects.filter(state="active", groupmilestone__due__lt=cut_off, groupmilestone__resolved="", groupmilestone__state="active").distinct()

