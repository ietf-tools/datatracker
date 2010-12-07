# expiry of Internet Drafts

from django.conf import settings
from django.template.loader import render_to_string
from django.db.models import Q

import datetime, os, shutil, glob, re

from ietf.idtracker.models import InternetDraft, IDDates, IDStatus, IDState, DocumentComment
from ietf.utils.mail import send_mail
from ietf.idrfc.utils import log_state_changed, add_document_comment

def in_id_expire_freeze(when=None):
    if when == None:
        when = datetime.datetime.now()
        
    d = IDDates.objects.get(id=IDDates.SECOND_CUT_OFF).date
    # for some reason, the old Perl code started at 9 am
    second_cut_off = datetime.datetime.combine(d, datetime.time(9, 0))
    
    d = IDDates.objects.get(id=IDDates.IETF_MONDAY).date
    ietf_monday = datetime.datetime.combine(d, datetime.time(0, 0))
    
    return second_cut_off <= when < ietf_monday

def get_expired_ids():
    cut_off = datetime.date.today() - datetime.timedelta(days=InternetDraft.DAYS_TO_EXPIRE)

    return InternetDraft.objects.filter(
        revision_date__lte=cut_off,
        status__status="Active",
        review_by_rfc_editor=0).filter(
        Q(idinternal=None) | Q(idinternal__cur_state__document_state_id__gte=42))

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
              dict(doc=doc))

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

            if doc.status_id == 3:
                if ext != ".txt":
                    move_file_to("unknown_ids")
            elif doc.status_id in (2, 4, 5, 6) and doc.expiration_date and doc.expiration_date < cut_off:
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
