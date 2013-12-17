# generation of mails 

import textwrap, datetime, re

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.text import wrap
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.mail import send_mail, send_mail_text

from ietf.group.models import *

def email_milestones_changed(request, group, changes):
    def wrap_up_email(to, text):
        text = wrap(strip_tags(text), 70)
        text += "\n\n"
        text += u"URL: %s" % (settings.IDTRACKER_BASE_URL + urlreverse("group_charter", kwargs=dict(acronym=group.acronym)))

        send_mail_text(request, to, None,
                       u"Milestones changed for %s %s" % (group.acronym, group.type.name),
                       text)

    # first send to AD and chairs
    to = []
    if group.ad:
        to.append(group.ad.role_email("ad").formatted_email())

    for r in group.role_set.filter(name="chair"):
        to.append(r.formatted_email())

    if to:
        wrap_up_email(to, u"\n\n".join(c + "." for c in changes))

    # then send to WG
    if group.list_email:
        review_re = re.compile("Added .* for review, due")
        to = [ group.list_email ]
        wrap_up_email(to, u"\n\n".join(c + "." for c in changes if not review_re.match(c)))


def email_milestone_review_reminder(group, grace_period=7):
    """Email reminders about milestones needing review to AD."""
    if not group.ad:
        return False

    to = [group.ad.role_email("ad").formatted_email()]
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
              "wginfo/reminder_milestones_need_review.txt",
              dict(group=group,
                   milestones=milestones,
                   url=settings.IDTRACKER_BASE_URL + urlreverse("wg_edit_milestones", kwargs=dict(acronym=group.acronym))
                   ))

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
              "wginfo/reminder_milestones_due.txt",
              dict(group=group,
                   milestones=milestones,
                   today=today,
                   early_warning_days=early_warning_days,
                   url=settings.IDTRACKER_BASE_URL + urlreverse("group_charter", kwargs=dict(acronym=group.acronym))
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
              "wginfo/reminder_milestones_overdue.txt",
              dict(group=group,
                   milestones=milestones,
                   url=settings.IDTRACKER_BASE_URL + urlreverse("group_charter", kwargs=dict(acronym=group.acronym))
                   ))

def groups_needing_milestones_overdue_reminder(grace_period=30):
    cut_off = datetime.date.today() - datetime.timedelta(days=grace_period)
    return Group.objects.filter(state="active", groupmilestone__due__lt=cut_off, groupmilestone__resolved="", groupmilestone__state="active").distinct()

