# expiry of Internet Drafts

from django.conf import settings

import datetime, os, shutil, glob, re
from pathlib import Path

from ietf.utils.mail import send_mail
from ietf.doc.models import Document, DocEvent, State, IESG_SUBSTATE_TAGS
from ietf.person.models import Person 
from ietf.meeting.models import Meeting
from ietf.doc.utils import add_state_change_event
from ietf.mailtrigger.utils import gather_address_lists


def expirable_draft(draft):
    """Return whether draft is in an expirable state or not. This is
    the single draft version of the logic in expirable_drafts. These
    two functions need to be kept in sync."""
    return (draft.expires and draft.get_state_slug() == "active"
            and draft.get_state_slug("draft-iesg") in (None, "watching", "dead")
            and draft.get_state_slug("draft-stream-%s" % draft.stream_id) not in ("rfc-edit", "pub")
            and not draft.tags.filter(slug="rfc-rev"))

def expirable_drafts():
    """Return a queryset with expirable drafts."""
    # the general rule is that each active draft is expirable, unless
    # it's in a state where we shouldn't touch it
    d = Document.objects.filter(states__type="draft", states__slug="active").exclude(expires=None)

    nonexpirable_states = []
    # all IESG states except AD Watching and Dead block expiry
    nonexpirable_states += list(State.objects.filter(used=True, type="draft-iesg").exclude(slug__in=("watching", "dead")))
    # sent to RFC Editor and RFC Published block expiry (the latter
    # shouldn't be possible for an active draft, though)
    nonexpirable_states += list(State.objects.filter(used=True, type__in=("draft-stream-iab", "draft-stream-irtf", "draft-stream-ise"), slug__in=("rfc-edit", "pub")))

    d = d.exclude(states__in=nonexpirable_states)

    # under review by the RFC Editor blocks expiry
    d = d.exclude(tags="rfc-rev")

    return d.distinct()

def get_soon_to_expire_drafts(days_of_warning):
    start_date = datetime.date.today() - datetime.timedelta(1)
    end_date = start_date + datetime.timedelta(days_of_warning)

    return expirable_drafts().filter(expires__gte=start_date, expires__lt=end_date)

def get_expired_drafts():
    return expirable_drafts().filter(expires__lt=datetime.date.today() + datetime.timedelta(1))

def in_draft_expire_freeze(when=None):
    if when == None:
        when = datetime.datetime.now()

    d = Meeting.get_second_cut_off()
    # for some reason, the old Perl code started at 9 am
    second_cut_off = datetime.datetime.combine(d, datetime.time(9, 0))

    d = Meeting.get_ietf_monday()
    ietf_monday = datetime.datetime.combine(d, datetime.time(0, 0))

    return second_cut_off <= when < ietf_monday

def send_expire_warning_for_draft(doc):
    if doc.get_state_slug("draft-iesg") == "dead":
        return # don't warn about dead documents

    expiration = doc.expires.date()

    (to,cc) = gather_address_lists('doc_expires_soon',doc=doc)

    s = doc.get_state("draft-iesg")
    state = s.name if s else "I-D Exists"

    frm = None
    request = None
    if to or cc:
        send_mail(request, to, frm,
                  u"Expiration impending: %s" % doc.file_tag(),
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
    state = s.name if s else "I-D Exists"

    request = None
    (to,cc) = gather_address_lists('doc_expired',doc=doc)
    send_mail(request, to,
              "I-D Expiring System <ietf-secretariat-reply@ietf.org>",
              u"I-D was expired %s" % doc.file_tag(),
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
                shutil.move(src, dst)
            except IOError as e:
                if "No such file or directory" in str(e):
                    pass
                else:
                    raise

    src_dir = Path(settings.INTERNET_DRAFT_PATH)
    for file in src_dir.glob("%s-%s.*" % (doc.name, rev)):
        move_file(str(file.name))

def expire_draft(doc):
    # clean up files
    move_draft_files_to_archive(doc, doc.rev)

    system = Person.objects.get(name="(System)")

    events = []

    # change the state
    if doc.latest_event(type='started_iesg_process'):
        new_state = State.objects.get(used=True, type="draft-iesg", slug="dead")
        prev_state = doc.get_state(new_state.type_id)
        prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
        if new_state != prev_state:
            doc.set_state(new_state)
            doc.tags.remove(*prev_tags)
            e = add_state_change_event(doc, system, prev_state, new_state, prev_tags=prev_tags, new_tags=[])
            if e:
                events.append(e)

    events.append(DocEvent.objects.create(doc=doc, by=system, type="expired_document", desc="Document has expired"))

    doc.set_state(State.objects.get(used=True, type="draft", slug="expired"))
    doc.save_with_history(events)

def clean_up_draft_files():
    """Move unidentified and old files out of the Internet Draft directory."""
    cut_off = datetime.date.today()

    pattern = os.path.join(settings.INTERNET_DRAFT_PATH, "draft-*.*")
    filename_re = re.compile('^(.*)-(\d\d)$')

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
            shutil.move(path,
                        os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, subdir, basename))

        try:
            doc = Document.objects.get(name=filename, rev=revision)

            state = doc.get_state_slug()

            if state in ("rfc","repl"):
                move_file_to("")
            elif state in ("expired", "auth-rm", "ietf-rm") and doc.expires and doc.expires.date() < cut_off:
                move_file_to("")

        except Document.DoesNotExist:
            move_file_to("unknown_ids")
