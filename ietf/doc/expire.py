# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-
# expiry of Internet-Drafts


import debug    # pyflakes:ignore

from django.conf import settings
from django.utils import timezone

import datetime, os, shutil, glob, re
from pathlib import Path

from typing import List, Optional      # pyflakes:ignore

from ietf.doc.utils import update_action_holders
from ietf.utils import log
from ietf.utils.mail import send_mail
from ietf.doc.models import Document, DocEvent, State
from ietf.person.models import Person 
from ietf.meeting.models import Meeting
from ietf.mailtrigger.utils import gather_address_lists
from ietf.utils.timezone import date_today, datetime_today, DEADLINE_TZINFO


nonexpirable_states: Optional[List[State]] = None

def expirable_drafts(queryset=None):
    """Return a queryset with expirable drafts."""
    global nonexpirable_states

    # the general rule is that each active draft is expirable, unless
    # it's in a state where we shouldn't touch it
    if not queryset:
        queryset = Document.objects.all()

    # Populate this first time through (but after django has been set up)
    if nonexpirable_states is None:
        # all IESG states except I-D Exists and Dead block expiry
        nonexpirable_states = list(State.objects.filter(used=True, type="draft-iesg").exclude(slug__in=("idexists", "dead")))
        # sent to RFC Editor and RFC Published block expiry (the latter
        # shouldn't be possible for an active draft, though)
        nonexpirable_states += list(State.objects.filter(used=True, type__in=("draft-stream-iab", "draft-stream-irtf", "draft-stream-ise"), slug__in=("rfc-edit", "pub")))
        # other IRTF states that block expiration
        nonexpirable_states += list(State.objects.filter(used=True, type_id="draft-stream-irtf", slug__in=("irsgpoll", "iesg-rev",)))

    return queryset.filter(
        states__type="draft", states__slug="active"
    ).exclude(
        expires=None
    ).exclude(
        states__in=nonexpirable_states
    ).exclude(
        tags="rfc-rev"  # under review by the RFC Editor blocks expiry
    ).distinct()


def get_soon_to_expire_drafts(days_of_warning):
    start_date = datetime_today(DEADLINE_TZINFO) - datetime.timedelta(1)
    end_date = start_date + datetime.timedelta(days_of_warning)

    return expirable_drafts().filter(expires__gte=start_date, expires__lt=end_date)

def get_expired_drafts():
    return expirable_drafts().filter(expires__lt=datetime_today(DEADLINE_TZINFO) + datetime.timedelta(1))

def in_draft_expire_freeze(when=None):
    if when == None:
        when = timezone.now()

    meeting = Meeting.objects.filter(type='ietf', date__gte=when-datetime.timedelta(days=7)).order_by('date').first()

    if not meeting:
        return False

    d = meeting.get_second_cut_off()
    # for some reason, the old Perl code started at 9 am
    second_cut_off = d.replace(hour=9, minute=0, second=0, microsecond=0)

    d = meeting.get_ietf_monday()
    ietf_monday = datetime.datetime.combine(d, datetime.time(0, 0), tzinfo=meeting.tz())

    return second_cut_off <= when < ietf_monday

def send_expire_warning_for_draft(doc):

    if ((doc.get_state_slug("draft-iesg") == "dead") or 
        (doc.get_state_slug("draft") != "active")):
        return # don't warn about dead or inactive documents

    expiration = doc.expires.astimezone(DEADLINE_TZINFO).date()
    now_plus_12hours = timezone.now() + datetime.timedelta(hours=12)
    soon = now_plus_12hours.date()
    if expiration <= soon:
        # The document will expire very soon, which will send email to the
        # same people, so do not send the warning at this point in time
        return


    (to,cc) = gather_address_lists('doc_expires_soon',doc=doc)

    s = doc.get_state("draft-iesg")
    log.assertion('s')
    state = s.name if s else "I-D Exists" # TODO remove the if clause after some runtime shows no assertions

    frm = None
    request = None
    if to or cc:
        send_mail(request, to, frm,
                  "Expiration impending: %s" % doc.file_tag(),
                  "doc/draft/expire_warning_email.txt",
                  dict(doc=doc,
                       state=state,
                       expiration=expiration
                       ),
                  cc=cc)

def send_expire_notice_for_draft(doc):
    if doc.get_state_slug("draft-iesg") == "dead":
        return

    s = doc.get_state("draft-iesg")
    log.assertion('s')
    state = s.name if s else "I-D Exists" # TODO remove the if clause after some rintime shows no assertions

    request = None
    (to,cc) = gather_address_lists('doc_expired',doc=doc)
    send_mail(request, to,
              "I-D Expiring System <ietf-secretariat-reply@ietf.org>",
              "I-D was expired %s" % doc.file_tag(),
              "doc/draft/id_expired_email.txt",
              dict(doc=doc,
                   state=state,
                   ),
              cc=cc)

def move_draft_files_to_archive(doc, rev):
    def move_file(f):
        src = os.path.join(settings.INTERNET_DRAFT_PATH, f)
        dst = os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, f)

        if os.path.exists(src):
            try:
                # ghostlinkd would keep this in the combined all archive since it would
                # be sourced from a different place. But when ghostlinkd is removed, nothing
                # new is needed here - the file will already exist in the combined archive
                shutil.move(src, dst)
            except IOError as e:
                if "No such file or directory" in str(e):
                    pass
                else:
                    raise
    
    def remove_ftp_copy(f):
        mark = Path(settings.FTP_DIR) / "internet-drafts" / f
        if mark.exists():
            mark.unlink()


    src_dir = Path(settings.INTERNET_DRAFT_PATH)
    for file in src_dir.glob("%s-%s.*" % (doc.name, rev)):
        move_file(str(file.name))
        remove_ftp_copy(str(file.name))

def expire_draft(doc):
    # clean up files
    move_draft_files_to_archive(doc, doc.rev)

    system = Person.objects.get(name="(System)")

    events = []

    events.append(DocEvent.objects.create(doc=doc, rev=doc.rev, by=system, type="expired_document", desc="Document has expired"))

    prev_draft_state=doc.get_state("draft")
    doc.set_state(State.objects.get(used=True, type="draft", slug="expired"))
    events.append(update_action_holders(doc, prev_draft_state, doc.get_state("draft"),[],[]))
    doc.save_with_history(events)

def clean_up_draft_files():
    """Move unidentified and old files out of the Internet-Draft directory."""
    cut_off = date_today(DEADLINE_TZINFO)

    pattern = os.path.join(settings.INTERNET_DRAFT_PATH, "draft-*.*")
    filename_re = re.compile(r'^(.*)-(\d\d)$')

    def splitext(fn):
        """
        Split the pathname path into a pair (root, ext) such that root + ext
        == path, and ext is empty or begins with a period and contains all
        periods in the last path component.

        This differs from os.path.splitext in the number of periods in the ext
        parts when the final path component contains more than one period.
        """
        s = fn.rfind("/")
        if s == -1:
            s = 0
        i = fn[s:].find(".")
        if i == -1:
            return fn, ''
        else:
            return fn[:s+i], fn[s+i:]

    for path in glob.glob(pattern):
        basename = os.path.basename(path)
        stem, ext = splitext(basename)
        match = filename_re.search(stem)
        if not match:
            filename, revision = ("UNKNOWN", "00")
        else:
            filename, revision = match.groups()

        def move_file_to(subdir):
            # Similar to move_draft_files_to_archive
            shutil.move(path,
                        os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, subdir, basename))
            mark = Path(settings.FTP_DIR) / "internet-drafts" / basename
            if mark.exists():
                mark.unlink()

        try:
            doc = Document.objects.get(name=filename, rev=revision)

            state = doc.get_state_slug()

            if state in ("rfc","repl"):
                move_file_to("")
            elif (state in ("expired", "auth-rm", "ietf-rm")
                  and doc.expires
                  and doc.expires.astimezone(DEADLINE_TZINFO).date() < cut_off):
                move_file_to("")

        except Document.DoesNotExist:
            # All uses of this past 2014 seem related to major system failures.
            move_file_to("unknown_ids")

