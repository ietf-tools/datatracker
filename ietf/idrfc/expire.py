# expiry of Internet Drafts

from django.conf import settings
from django.template.loader import render_to_string
from django.db.models import Q

import datetime, os, shutil, glob, re, itertools

from ietf.idtracker.models import InternetDraft, IDDates, IDStatus, IDState, DocumentComment, IDAuthor, WGChair
from ietf.utils.mail import send_mail, send_mail_subj
from ietf.idrfc.utils import log_state_changed, add_document_comment
from ietf.doc.models import Document, DocEvent, save_document_in_history, State
from ietf.name.models import DocTagName
from ietf.person.models import Person, Email
from ietf.meeting.models import Meeting

def in_id_expire_freeze(when=None):
    if when == None:
        when = datetime.datetime.now()

    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        d = Meeting.get_second_cut_off()
    else:
        d = IDDates.objects.get(id=IDDates.SECOND_CUT_OFF).date
    # for some reason, the old Perl code started at 9 am
    second_cut_off = datetime.datetime.combine(d, datetime.time(9, 0))
    
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        d = Meeting.get_ietf_monday()
    else:
        d = IDDates.objects.get(id=IDDates.IETF_MONDAY).date
    ietf_monday = datetime.datetime.combine(d, datetime.time(0, 0))
    
    return second_cut_off <= when < ietf_monday

def expirable_documents():
    # the general rule is that each active draft is expirable, unless
    # it's in a state where we shouldn't touch it

    d = Document.objects.filter(states__type="draft", states__slug="active").exclude(tags="rfc-rev")

    nonexpirable_states = []
    # all IESG states except AD Watching and Dead block expiry
    nonexpirable_states += list(State.objects.filter(type="draft-iesg").exclude(slug__in=("watching", "dead")))
    # Sent to RFC Editor and RFC Published block expiry (the latter
    # shouldn't be possible for an active draft, though)
    nonexpirable_states += list(State.objects.filter(type__in=("draft-stream-iab", "draft-stream-irtf", "draft-stream-ise"), slug__in=("rfc-edit", "pub")))

    return d.exclude(states__in=nonexpirable_states).distinct()

def get_soon_to_expire_ids(days):
    start_date = datetime.date.today() - datetime.timedelta(InternetDraft.DAYS_TO_EXPIRE - 1)
    end_date = start_date + datetime.timedelta(days - 1)
    
    for d in InternetDraft.objects.filter(revision_date__gte=start_date,revision_date__lte=end_date,status__status='Active'):
        if d.can_expire():
            yield d

def get_soon_to_expire_idsREDESIGN(days):
    start_date = datetime.date.today() - datetime.timedelta(1)
    end_date = start_date + datetime.timedelta(days - 1)
    
    for d in expirable_documents():
        if d.expires and start_date <= d.expires.date() <= end_date:
            yield d

def get_expired_ids():
    cut_off = datetime.date.today() - datetime.timedelta(days=InternetDraft.DAYS_TO_EXPIRE)

    return InternetDraft.objects.filter(
        revision_date__lte=cut_off,
        status__status="Active",
        review_by_rfc_editor=0).filter(
        Q(idinternal=None) | Q(idinternal__cur_state__document_state_id__gte=42))

def get_expired_idsREDESIGN():
    today = datetime.date.today()

    for d in expirable_documents():
        if d.expires and d.expires.date() <= today:
            yield d

def send_expire_warning_for_id(doc):
    expiration = doc.expiration()
    # Todo:
    #second_cutoff = IDDates.objects.get(date_id=2)
    #ietf_monday = IDDates.objects.get(date_id=3)
    #freeze_delta = ietf_monday - second_cutoff
    #   # The I-D expiration job doesn't run while submissions are frozen.
    #   if ietf_monday > expiration > second_cutoff:
    #       expiration += freeze_delta
    
    authors = doc.authors.all()
    to_addrs = [author.email() for author in authors if author.email()]
    cc_addrs = None
    if doc.group.acronym != 'none':
        cc_addrs = [chair.person.email() for chair in WGChair.objects.filter(group_acronym=doc.group)]

    if to_addrs or cc_addrs:
        send_mail_subj(None, to_addrs, None, 'notify_expirations/subject.txt', 'notify_expirations/body.txt', 
                   {
                      'draft':doc,
                      'expiration':expiration,
                   },
                   cc_addrs)

def send_expire_warning_for_idREDESIGN(doc):
    if doc.get_state_slug("draft-iesg") == "dead":
        return # don't warn about dead documents

    expiration = doc.expires.date()

    to = [e.formatted_email() for e in doc.authors.all() if not e.address.startswith("unknown-email")]
    cc = None
    if doc.group.type_id in ("wg", "rg"):
        cc = [e.formatted_email() for e in Email.objects.filter(role__group=doc.group, role__name="chair") if not e.address.startswith("unknown-email")]

    s = doc.get_state("draft-iesg")
    state = s.name if s else "I-D Exists"
        
    frm = None
    request = None
    if to or cc:
        send_mail(request, to, frm,
                  u"Expiration impending: %s" % doc.file_tag(),
                  "idrfc/expire_warning_email.txt",
                  dict(doc=doc,
                       state=state,
                       expiration=expiration
                       ),
                  cc=cc)

def send_expire_notice_for_id(doc):
    doc.dunn_sent_date = datetime.date.today()
    doc.save()

    if not doc.idinternal:
        return
    
    request = None
    to = u"%s <%s>" % doc.idinternal.job_owner.person.email()
    send_mail(request, to,
              "I-D Expiring System <ietf-secretariat-reply@ietf.org>",
              u"I-D was expired %s" % doc.file_tag(),
              "idrfc/id_expired_email.txt",
              dict(doc=doc,
                   state=doc.idstate()))

def send_expire_notice_for_idREDESIGN(doc):
    if not doc.ad or doc.get_state_slug("draft-iesg") == "dead":
        return

    s = doc.get_state("draft-iesg")
    state = s.name if s else "I-D Exists"

    request = None
    to = doc.ad.role_email("ad").formatted_email()
    send_mail(request, to,
              "I-D Expiring System <ietf-secretariat-reply@ietf.org>",
              u"I-D was expired %s" % doc.file_tag(),
              "idrfc/id_expired_email.txt",
              dict(doc=doc,
                   state=state,
                   ))

def expire_id(doc):
    def move_file(f):
        src = os.path.join(settings.INTERNET_DRAFT_PATH, f)
        dst = os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, f)

        if os.path.exists(src):
            shutil.move(src, dst)

    move_file("%s-%s.txt" % (doc.filename, doc.revision_display()))
    move_file("%s-%s.txt.p7s" % (doc.filename, doc.revision_display()))
    move_file("%s-%s.ps" % (doc.filename, doc.revision_display()))
    move_file("%s-%s.pdf" % (doc.filename, doc.revision_display()))

    new_revision = "%02d" % (int(doc.revision) + 1)

    new_file = open(os.path.join(settings.INTERNET_DRAFT_PATH, "%s-%s.txt" % (doc.filename, new_revision)), 'w')
    txt = render_to_string("idrfc/expire_text.txt",
                           dict(doc=doc,
                                authors=[a.person.email() for a in doc.authors.all()],
                                expire_days=InternetDraft.DAYS_TO_EXPIRE))          
    new_file.write(txt)
    new_file.close()
    
    doc.revision = new_revision
    doc.expiration_date = datetime.date.today()
    doc.last_modified_date = datetime.date.today()
    doc.status = IDStatus.objects.get(status="Expired")
    doc.save()

    if doc.idinternal:
        if doc.idinternal.cur_state_id != IDState.DEAD:
            doc.idinternal.change_state(IDState.objects.get(document_state_id=IDState.DEAD), None)
            log_state_changed(None, doc, "system")

        add_document_comment(None, doc, "Document is expired by system")

def move_draft_files_to_archive(doc, rev):
    def move_file(f):
        src = os.path.join(settings.INTERNET_DRAFT_PATH, f)
        dst = os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, f)

        if os.path.exists(src):
            shutil.move(src, dst)

    file_types = ['txt', 'txt.p7s', 'ps', 'pdf']
    for t in file_types:
        move_file("%s-%s.%s" % (doc.name, rev, t))

def expire_idREDESIGN(doc):
    # clean up files
    move_draft_files_to_archive(doc, doc.rev)

    # change the state
    system = Person.objects.get(name="(System)")

    save_document_in_history(doc)
    if doc.latest_event(type='started_iesg_process'):
        dead_state = State.objects.get(type="draft-iesg", slug="dead")
        prev = doc.get_state("draft-iesg")
        prev_tag = doc.tags.filter(slug__in=('point', 'ad-f-up', 'need-rev', 'extpty'))
        prev_tag = prev_tag[0] if prev_tag else None
        if prev != dead_state:
            doc.set_state(dead_state)
            if prev_tag:
                doc.tags.remove(prev_tag)
            log_state_changed(None, doc, system, prev, prev_tag)

        e = DocEvent(doc=doc, by=system)
        e.type = "expired_document"
        e.desc = "Document has expired"
        e.save()

    doc.set_state(State.objects.get(type="draft", slug="expired"))
    doc.time = datetime.datetime.now()
    doc.save()

def clean_up_id_files():
    """Move unidentified and old files out of the Internet Draft directory."""
    cut_off = datetime.date.today() - datetime.timedelta(days=InternetDraft.DAYS_TO_EXPIRE)

    pattern = os.path.join(settings.INTERNET_DRAFT_PATH, "draft-*.*")
    files = []
    filename_re = re.compile('^(.*)-(\d\d)$')

    def splitext(fn):
        """
        Split the pathname path into a pair (root, ext) such that root + ext
        == path, and ext is empty or begins with a period and contains all
        periods in the last path component.

        This differs from os.path.splitext in the number of periods in the ext
        parts when the final path component containt more than one period.
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
            doc = InternetDraft.objects.get(filename=filename, revision=revision)

            if doc.status_id == 3:      # RFC
                if ext != ".txt":
                    move_file_to("unknown_ids")
            elif doc.status_id in (2, 4, 5, 6) and doc.expiration_date and doc.expiration_date < cut_off:
                # Expired, Withdrawn by Auth, Replaced, Withdrawn by IETF,
                # and expired more than DAYS_TO_EXPIRE ago
                if os.path.getsize(path) < 1500:
                    move_file_to("deleted_tombstones")
                    # revert version after having deleted tombstone
                    doc.revision = "%02d" % (int(revision) - 1)
                    doc.expired_tombstone = True
                    doc.save()
                else:
                    move_file_to("expired_without_tombstone")
            
        except InternetDraft.DoesNotExist:
            move_file_to("unknown_ids")

def clean_up_id_filesREDESIGN():
    """Move unidentified and old files out of the Internet Draft directory."""
    cut_off = datetime.date.today()

    pattern = os.path.join(settings.INTERNET_DRAFT_PATH, "draft-*.*")
    files = []
    filename_re = re.compile('^(.*)-(\d\d)$')
    
    def splitext(fn):
        """
        Split the pathname path into a pair (root, ext) such that root + ext
        == path, and ext is empty or begins with a period and contains all
        periods in the last path component.

        This differs from os.path.splitext in the number of periods in the ext
        parts when the final path component containt more than one period.
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

            if state == "rfc":
                if ext != ".txt":
                    move_file_to("unknown_ids")
            elif state in ("expired", "repl", "auth-rm", "ietf-rm") and doc.expires and doc.expires.date() < cut_off:
                # Expired, Replaced, Withdrawn by Author/IETF, and expired
                if os.path.getsize(path) < 1500:
                    # we don't make tombstones any more so this should
                    # go away in the future
                    move_file_to("deleted_tombstones")
                else:
                    move_file_to("expired_without_tombstone")
            
        except Document.DoesNotExist:
            move_file_to("unknown_ids")

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    get_soon_to_expire_ids = get_soon_to_expire_idsREDESIGN
    get_expired_ids = get_expired_idsREDESIGN
    send_expire_warning_for_id = send_expire_warning_for_idREDESIGN
    send_expire_notice_for_id = send_expire_notice_for_idREDESIGN
    expire_id = expire_idREDESIGN
    clean_up_id_files = clean_up_id_filesREDESIGN
