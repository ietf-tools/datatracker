# Copyright The IETF Trust 2020 All Rights Reserved

import os

from django.conf import settings
from django.db import migrations


class Helper(object):

    def __init__(self, review_path, comments_by, document_class):
        self.review_path = review_path
        self.comments_by = comments_by
        self.document_class = document_class

    def remove_file(self,name):
        filename = os.path.join(self.review_path, '{}.txt'.format(name))
        os.remove(filename)

    def rename_file(self, old_name, new_name):
        old_filename = os.path.join(self.review_path, '{}.txt'.format(old_name))
        new_filename = os.path.join(self.review_path, '{}.txt'.format(new_name))
        os.rename(old_filename, new_filename)

    def add_comment(self, name, comment):
        doc = self.document_class.objects.get(name=name)
        doc.docevent_set.create(
            type = 'added_comment',
            by = self.comments_by,
            rev = doc.rev,
            desc = comment,
        )

def forward(apps, schema_editor):
    ReviewAssignment = apps.get_model('review','ReviewAssignment')
    Document = apps.get_model('doc','Document')
    Person = apps.get_model('person','Person')

    # The calculation of review_path makes the assumption that DOCUMENT_PATH_PATTERN only uses 
    # things that are invariant for review documents. For production, as of this commit, that's 
    # DOCUMENT_PATH_PATTERN = '/a/www/ietf-ftp/{doc.type_id}/'

    helper = Helper(
        review_path = settings.DOCUMENT_PATH_PATTERN.format(doc=Document.objects.filter(type_id='review').last()),
        comments_by = Person.objects.get(name='(System)'),
        document_class = Document,
    )

    # review-allan-5g-fmc-encapsulation-04-tsvart-lc-black is a double-submit
    # In [120]: for d in Document.objects.filter(name__contains='review-allan-5g-fmc-encapsulation-04-tsvart
    #      ...: ').order_by('name'):
    #      ...:     print(d.name, d.time)
    #      ...:
    # review-allan-5g-fmc-encapsulation-04-tsvart-lc-black-2020-06-30 2020-06-30 11:06:30
    # review-allan-5g-fmc-encapsulation-04-tsvart-lc-black-2020-06-30-2 2020-06-30 11:06:30
    # (I've put some more detail below on this as my understanding of double-submit improved)
    # The recommendation is to point the reviewassignment at the first submission, and delete the -2.
    #   
    a = ReviewAssignment.objects.get(review_request__doc__name='draft-allan-5g-fmc-encapsulation', review_request__team__acronym='tsvart')
    a.review = Document.objects.get(name='review-allan-5g-fmc-encapsulation-04-tsvart-lc-black-2020-06-30')
    a.save()
    Document.objects.filter(name='review-allan-5g-fmc-encapsulation-04-tsvart-lc-black-2020-06-30-2').delete()
    helper.remove_file('review-allan-5g-fmc-encapsulation-04-tsvart-lc-black-2020-06-30-2')
    helper.add_comment('draft-allan-5g-fmc-encapsulation', 'Removed an unintended duplicate version of the tsvart lc review')


    # This one is just simply disconnected. No duplicates or anything to remove.
    a = ReviewAssignment.objects.get(review_request__doc__name='draft-ietf-6lo-minimal-fragment',review_request__team__acronym='opsdir')
    r = Document.objects.get(name='review-ietf-6lo-minimal-fragment-09-opsdir-lc-banks-2020-01-31')
    a.review = r
    a.state_id = 'completed'
    a.result_id = 'nits'
    a.reviewed_rev = '09'
    a.completed_on = r.time
    a.save()
    helper.add_comment('draft-ietf-6lo-minimal-fragment', 'Reconnected opsdir lc review')

    # This review took place when we were spinning up the review tool. I suspect there were bugs at the time that we no longer have insight into.
    # These two do not exist on disk
    # review-ietf-6lo-privacy-considerations-04-secdir-lc-kaduk-2016-11-30
    # review-ietf-6lo-privacy-considerations-04-secdir-lc-kaduk-2016-11-30-2
    # These are identical except for 0d0a vs 0a and newline at end of file
    # review-ietf-6lo-privacy-considerations-04-secdir-lc-kaduk-2016-11-30-3
    # review-ietf-6lo-privacy-considerations-04-secdir-lc-kaduk-2016-12-01
    # -12-01 is already reachable from the assignment. I suggest:
    Document.objects.filter(name__startswith='review-ietf-6lo-privacy-considerations-04-secdir-lc-kaduk-2016-11-30').delete()
    helper.remove_file('review-ietf-6lo-privacy-considerations-04-secdir-lc-kaduk-2016-11-30-3')
    helper.add_comment('draft-ietf-6lo-privacy-considerations','Removed unintended duplicates of secdir lc review')

    a = ReviewAssignment.objects.get(review_request__doc__name='draft-ietf-bess-nsh-bgp-control-plane',review_request__team__acronym='rtgdir',reviewer__person__name__icontains='singh')
    r = Document.objects.get(name='review-ietf-bess-nsh-bgp-control-plane-13-rtgdir-lc-singh-2020-01-29')
    a.review = r
    a.state_id = 'completed'
    a.reviewed_rev='13'
    a.result_id='issues'
    a.completed_on=r.time
    a.save()
    helper.add_comment('draft-ietf-bess-nsh-bgp-control-plane','Reconnected rtgdir lc review')

    # In [121]: for d in Document.objects.filter(name__contains='review-ietf-capport-architecture-08-genart-lc-halpern').order_by('name'):
    #      ...:     print(d.name, d.time)
    # review-ietf-capport-architecture-08-genart-lc-halpern-2020-05-16 2020-05-16 15:34:35
    # review-ietf-capport-architecture-08-genart-lc-halpern-2020-05-16-2 2020-05-16 15:35:55
    # Not the same as the other double-submits, but likely a failure on the first submit midway through processing that led to the second.
    # rjsparks@ietfa:/a/www/ietf-ftp/review> ls review-ietf-capport-architecture-08-genart-lc-halpern*
    # review-ietf-capport-architecture-08-genart-lc-halpern-2020-05-16-2.txt
    # Only -2 exists on disk
    # -2 is what is currently pointed to by the review assignment.
    helper.rename_file('review-ietf-capport-architecture-08-genart-lc-halpern-2020-05-16-2','review-ietf-capport-architecture-08-genart-lc-halpern-2020-05-16')
    a = ReviewAssignment.objects.get(review_request__doc__name='draft-ietf-capport-architecture',review_request__type_id='lc',reviewer__person__name='Joel M. Halpern')
    a.review = Document.objects.get(name='review-ietf-capport-architecture-08-genart-lc-halpern-2020-05-16')
    a.save()
    Document.objects.filter(name='review-ietf-capport-architecture-08-genart-lc-halpern-2020-05-16-2').delete()    
    helper.add_comment('draft-ietf-capport-architecture','Removed an unintended duplicate version of the genart lc review')
    # Any external references to -05-16-2 will now break, but I'm reticent to start down the path of putting something sensical there. 
    # Right now, any review document not pointed to by a reviewassignment is a database error, and the view code assumes it won't happen. 
    # We can make it more robust against crashing, but I don't think we should try to adapt the models to model the corruption.


    # Opsdir last call review of draft-ietf-cbor-array-tags-07
    # Got sent to the opsdir list (which is has a private archive) twice - no resulting thread from either
    # rjsparks@ietfa:/a/www/ietf-ftp/review> ls review-ietf-cbor-array-tags-07-opsdir-lc-dunbar*
    # review-ietf-cbor-array-tags-07-opsdir-lc-dunbar-2019-08-26-2.txt
    # review-ietf-cbor-array-tags-07-opsdir-lc-dunbar-2019-08-26.txt
    # In [122]: for d in Document.objects.filter(name__contains='review-ietf-cbor-array-tags-07-opsdir-lc-dunbar').order_by('name'):
    #      ...:     print(d.name, d.time)
    # review-ietf-cbor-array-tags-07-opsdir-lc-dunbar-2019-08-26 2019-08-26 14:13:29
    # review-ietf-cbor-array-tags-07-opsdir-lc-dunbar-2019-08-26-2 2019-08-26 14:13:29
    # This is a double-submit.
    # The ReviewAssignment already points to 08-26
    Document.objects.filter(name='review-ietf-cbor-array-tags-07-opsdir-lc-dunbar-2019-08-26-2').delete()
    helper.remove_file('review-ietf-cbor-array-tags-07-opsdir-lc-dunbar-2019-08-26-2')
    helper.add_comment('draft-ietf-cbor-array-tags','Removed unintended duplicate of opsdir lc review')

    # In [73]: for d in Document.objects.filter(name__startswith='review-ietf-detnet-mpls-over-udp-ip'):
    #     ...:     print(d.name, d.time)
    # <snip/>
    # review-ietf-detnet-mpls-over-udp-ip-06-genart-lc-holmberg-2020-09-01 2020-09-01 13:47:55
    # review-ietf-detnet-mpls-over-udp-ip-06-genart-lc-holmberg-2020-09-01-2 2020-09-01 13:47:55
    # review-ietf-detnet-mpls-over-udp-ip-06-opsdir-lc-romascanu-2020-09-03 2020-09-03 02:49:33
    # review-ietf-detnet-mpls-over-udp-ip-06-opsdir-lc-romascanu-2020-09-03-2 2020-09-03 02:49:33
    # <snip/>
    # Both of those are places where the submit button got hit twice in rapid successsion.
    # Messages went to the list twice. No threads were started
    # The review assignments currently point to the -2 versions. I think we change them to point to the not -2 versions and delete the -2 version documents.
    #
    a = ReviewAssignment.objects.get(review__name='review-ietf-detnet-mpls-over-udp-ip-06-genart-lc-holmberg-2020-09-01-2')
    a.review = Document.objects.get(name='review-ietf-detnet-mpls-over-udp-ip-06-genart-lc-holmberg-2020-09-01')
    a.save()
    Document.objects.filter(name='review-ietf-detnet-mpls-over-udp-ip-06-genart-lc-holmberg-2020-09-01-2').delete()
    helper.remove_file('review-ietf-detnet-mpls-over-udp-ip-06-genart-lc-holmberg-2020-09-01-2')
    #
    a = ReviewAssignment.objects.get(review__name='review-ietf-detnet-mpls-over-udp-ip-06-opsdir-lc-romascanu-2020-09-03-2')
    a.review = Document.objects.get(name='review-ietf-detnet-mpls-over-udp-ip-06-opsdir-lc-romascanu-2020-09-03')
    a.save()
    Document.objects.filter(name='review-ietf-detnet-mpls-over-udp-ip-06-opsdir-lc-romascanu-2020-09-03-2').delete()
    helper.remove_file('review-ietf-detnet-mpls-over-udp-ip-06-opsdir-lc-romascanu-2020-09-03-2')
    helper.add_comment('draft-ietf-detnet-mpls-over-udp-ip','Removed unintended duplicate of opsdir and genart lc reviews')

    # This draft had a contentious last call (not because of this review)
    # rjsparks@ietfa:/a/www/ietf-ftp/review> ls -l review-ietf-dprive-rfc7626-bis-03-genart*
    # -rw-r--r-- 1 wwwrun www 1087 Dec  4  2019 review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04-2.txt
    # -rw-r--r-- 1 wwwrun www 1087 Dec  4  2019 review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04-3.txt
    # -rw-r--r-- 1 wwwrun www 1087 Dec  4  2019 review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04.txt
    # These files are identical.
    # In [75]: Document.objects.filter(name__startswith='review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04').values_list('time',flat=True)
    # Out[75]: <QuerySet [datetime.datetime(2019, 12, 4, 13, 40, 30), datetime.datetime(2019, 12, 4, 13, 40, 30), datetime.datetime(2019, 12, 4, 13, 40, 32)]>
    # So again, the submit button got hit several times in rapid succession
    # Interestingly, this was a case where the review was sent to the list first and then Meral told the datatracker about it, so it's only on the list(s) once.
    # I think we change the assignment to point to 12-04 and delete -2 and -3.
    a = ReviewAssignment.objects.get(review__name='review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04-3')
    a.review = Document.objects.get(name='review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04')
    a.save()
    Document.objects.filter(name__startswith='review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04-').delete()
    helper.remove_file('review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04-2')
    helper.remove_file('review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04-3')
    helper.add_comment('draft-ietf-dprive-rfc7626-bis','Removed unintended duplicates of genart lc review')

    # In [76]: Document.objects.filter(name__startswith='review-ietf-emu-rfc5448bis-06-secdir-lc-rose')
    # Out[76]: <QuerySet [<Document: review-ietf-emu-rfc5448bis-06-secdir-lc-rose-2020-01-27>, <Document: review-ietf-emu-rfc5448bis-06-secdir-lc-rose-2020-02-06>]>
    # rjsparks@ietfa:/a/www/ietf-ftp/review> ls review-ietf-emu-rfc5448bis-06-secdir-lc-rose*
    # review-ietf-emu-rfc5448bis-06-secdir-lc-rose-2020-02-06.txt
    # review assignment points to 02-06.
    # Suggest we delete -01-27 Document object. There's nothing matching on disk to remove.
    Document.objects.filter(name='review-ietf-emu-rfc5448bis-06-secdir-lc-rose-2020-01-27').delete()
    helper.add_comment('draft-ietf-emu-rfc5448bis','Removed duplicate secdir lc review')

    # rjsparks@ietfa:/a/www/ietf-ftp/review> ls review-ietf-mmusic-t140-usage-data-channel-11-tsvart*
    # review-ietf-mmusic-t140-usage-data-channel-11-tsvart-lc-scharf-2020-01-28.txt
    # review-ietf-mmusic-t140-usage-data-channel-11-tsvart-lc-scharf-2020-03-27.txt
    # The second was derived from the list post, so it has "Reviewer: Michael Scharf Review result: Ready with Nits" added and is reflowed, but is otherwise identical.
    # In [80]: Document.objects.filter(name__startswith='review-ietf-mmusic-t140-usage
    #     ...: -data-channel-11-tsvart-lc-scharf')
    # Out[80]: <QuerySet [<Document: review-ietf-mmusic-t140-usage-data-channel-11-tsvart-lc-scharf-2020-01-28>, <Document: review-ietf-mmusic-t140-usage-data-channel-11-tsvart-lc-scharf-2020-03-27>]>
    # the 03-27 version was a resubmission by a secretary (Wes). The assignment currently points to 03-07, and it points to the 01-29 (! date there is in UTC) list entry.
    # 01-29 is in the window of confusion.
    # Suggest we just delete the -01-28 document object.
    Document.objects.filter(name='review-ietf-mmusic-t140-usage-data-channel-11-tsvart-lc-scharf-2020-01-28').delete()
    helper.remove_file('review-ietf-mmusic-t140-usage-data-channel-11-tsvart-lc-scharf-2020-01-28')
    helper.add_comment('draft-ietf-mmusic-t140-usage-data-channel','Removed duplicate tsvart lc review')

    # In [81]: Document.objects.filter(name__startswith='review-ietf-mpls-spl-terminology-03-opsdir-lc-jaeggli').values_list('time',flat=True)
    # Out[81]: <QuerySet [datetime.datetime(2020, 8, 15, 16, 38, 37), datetime.datetime(2020, 8, 15, 16, 38, 37)]>
    # Another double-submit.
    # The review assignment already points to -08-15. Suggest we delete -08-15-2
    Document.objects.filter(name='review-ietf-mpls-spl-terminology-03-opsdir-lc-jaeggli-2020-08-15-2').delete()
    helper.remove_file('review-ietf-mpls-spl-terminology-03-opsdir-lc-jaeggli-2020-08-15-2')
    helper.add_comment('draft-ietf-mpls-spl-terminology','Removed unintended duplicate opsdir lc review')


    # In [82]: Document.objects.filter(name__startswith='review-ietf-netconf-subscribed-notifications-23-rtgdir').values_list('time',flat=True)
    # Out[82]: <QuerySet [datetime.datetime(2019, 4, 16, 3, 45, 4), datetime.datetime(2019, 4, 16, 3, 45, 6)]>
    # Another double-submit. This time the second won and the review assignments points to -2. I suggest we change it to point to the base and delete -2.
    a = ReviewAssignment.objects.get(review__name='review-ietf-netconf-subscribed-notifications-23-rtgdir-lc-singh-2019-04-16-2')
    a.review = Document.objects.get(name='review-ietf-netconf-subscribed-notifications-23-rtgdir-lc-singh-2019-04-16')
    a.save()
    Document.objects.filter(name='review-ietf-netconf-subscribed-notifications-23-rtgdir-lc-singh-2019-04-16-2').delete()
    helper.remove_file('review-ietf-netconf-subscribed-notifications-23-rtgdir-lc-singh-2019-04-16-2')
    helper.add_comment('draft-ietf-netconf-subscribed-notifications','Removed unintended duplicate rtgdir lc review')

    # In [84]: Document.objects.filter(name__contains='ietf-netconf-yang-push-22-genart-lc-bryant').values_list('time',flat=True)
    # Out[84]: <QuerySet [datetime.datetime(2019, 4, 10, 13, 40, 41), datetime.datetime(2019, 4, 10, 13, 40, 41)]>
    # In [85]: ReviewAssignment.objects.get(review__name__contains='ietf-netconf-yang-
    #     ...: push-22-genart-lc-bryant').review
    # Out[85]: <Document: review-ietf-netconf-yang-push-22-genart-lc-bryant-2019-04-10-2>
    # Same as above.
    a = ReviewAssignment.objects.get(review__name='review-ietf-netconf-yang-push-22-genart-lc-bryant-2019-04-10-2')
    a.review = Document.objects.get(name='review-ietf-netconf-yang-push-22-genart-lc-bryant-2019-04-10')
    a.save()
    Document.objects.filter(name='review-ietf-netconf-yang-push-22-genart-lc-bryant-2019-04-10-2').delete()
    helper.remove_file('review-ietf-netconf-yang-push-22-genart-lc-bryant-2019-04-10-2')
    helper.add_comment('draft-ietf-netconf-yang-push','Removed unintended duplicate genart lc review')

    # In [92]: for d in Document.objects.filter(name__contains='ietf-nfsv4-rpcrdma-cm-pvt-data-06').order_by('name'):
    #     ...:     print(d.name, d.external_url)
    #     ...:
    # review-ietf-nfsv4-rpcrdma-cm-pvt-data-06-genart-lc-nandakumar-2020-01-27 https://mailarchive.ietf.org/arch/msg/gen-art/b'rGU9fbpAGtmz55Rcdfnl9ZsqMIo'
    # review-ietf-nfsv4-rpcrdma-cm-pvt-data-06-genart-lc-nandakumar-2020-01-30 https://mailarchive.ietf.org/arch/msg/gen-art/rGU9fbpAGtmz55Rcdfnl9ZsqMIo
    # review-ietf-nfsv4-rpcrdma-cm-pvt-data-06-opsdir-lc-comstedt-2020-01-27 https://mailarchive.ietf.org/arch/msg/ops-dir/b'BjEE4Y0ZDRALgueoS_lbL5U06js'
    # review-ietf-nfsv4-rpcrdma-cm-pvt-data-06-opsdir-lc-comstedt-2020-02-10 https://mailarchive.ietf.org/arch/msg/ops-dir/BjEE4Y0ZDRALgueoS_lbL5U06js
    # review-ietf-nfsv4-rpcrdma-cm-pvt-data-06-secdir-lc-sheffer-2020-01-26 https://mailarchive.ietf.org/arch/msg/secdir/hY6OTDbplzp9uONAvEjkcfa-N4A
    # This straddled the period of confusion.
    # For genart, Jean completed the review for the reviewer twice
    # for opsdir the reviewer submitted on different dates.
    # In both cases, the review only went to the list once, (the links above that are b'<>' are broken anyhow).
    # rjsparks@ietfa:/a/www/ietf-ftp/review> ls review-ietf-nfsv4-rpcrdma-cm-pvt-data-06-genart-lc-nandakumar*
    # review-ietf-nfsv4-rpcrdma-cm-pvt-data-06-genart-lc-nandakumar-2020-01-30.txt
    # rjsparks@ietfa:/a/www/ietf-ftp/review> ls review-ietf-nfsv4-rpcrdma-cm-pvt-data-06-opsdir-lc-comstedt*
    # review-ietf-nfsv4-rpcrdma-cm-pvt-data-06-opsdir-lc-comstedt-2020-02-10.txt
    # The review assignment objects point to the ones that are backed by disk files. I suggest we delete the others.
    Document.objects.filter(name='review-ietf-nfsv4-rpcrdma-cm-pvt-data-06-genart-lc-nandakumar-2020-01-27').delete()
    Document.objects.filter(name='review-ietf-nfsv4-rpcrdma-cm-pvt-data-06-opsdir-lc-comstedt-2020-01-27').delete()
    ReviewAssignment.objects.filter(review_request__doc__name='draft-ietf-nfsv4-rpcrdma-cm-pvt-data').exclude(review__type_id='review').delete()
    helper.add_comment('draft-ietf-nfsv4-rpcrdma-cm-pvt-data','Removed unintended duplicate genart and opsdir lc reviews')
    
    # In [101]: ReviewAssignment.objects.filter(review__name__contains='review-ietf-pce-pcep-flowspec-09-tsvart').values_list('review__name',flat=True)
    # Out[101]: <QuerySet ['review-ietf-pce-pcep-flowspec-09-tsvart-lc-touch-2020-07-03-2']>
    # In [102]: for d in Document.objects.filter(name__contains='review-ietf-pce-pcep-flowspec-09-tsvart').order_by('name'):
    #      ...:     print(d.name, d.time)
    # review-ietf-pce-pcep-flowspec-09-tsvart-lc-touch-2020-07-03 2020-07-03 19:20:49
    # review-ietf-pce-pcep-flowspec-09-tsvart-lc-touch-2020-07-03-2 2020-07-03 19:20:49
    # Same as double-submits above. 
    a = ReviewAssignment.objects.get(review__name='review-ietf-pce-pcep-flowspec-09-tsvart-lc-touch-2020-07-03-2')
    a.review = Document.objects.get(name='review-ietf-pce-pcep-flowspec-09-tsvart-lc-touch-2020-07-03')
    a.save()
    Document.objects.filter(name='review-ietf-pce-pcep-flowspec-09-tsvart-lc-touch-2020-07-03-2').delete()
    helper.remove_file('review-ietf-pce-pcep-flowspec-09-tsvart-lc-touch-2020-07-03-2')
    helper.add_comment('draft-ietf-pce-pcep-flowspec','Removed unintended duplicate tsvart lc review')

    # draft-ietf-pim-msdp-yang history is a bit more complicated.
    # It is currently (23Sep2020) in AUTH48...
    # There is a combination of secretaries trying to route around the confusion and a reviewer accidentally updating the wrong review.
    # Everything went to lists.
    # In [110]: for rq in ReviewRequest.objects.filter(doc__name__contains='ietf-pim-msdp-yang'):
    #      ...:     print(rq)
    # Early review on draft-ietf-pim-msdp-yang by YANG Doctors Assigned
    # Last Call review on draft-ietf-pim-msdp-yang by YANG Doctors Assigned
    # Last Call review on draft-ietf-pim-msdp-yang by Routing Area Directorate Assigned
    # Last Call review on draft-ietf-pim-msdp-yang by General Area Review Team (Gen-ART) Overtaken by Events
    # Last Call review on draft-ietf-pim-msdp-yang by Security Area Directorate Overtaken by Events
    # Last Call review on draft-ietf-pim-msdp-yang by Ops Directorate Assigned
    # Last Call review on draft-ietf-pim-msdp-yang by Transport Area Review Team Team Will not Review Document
    # Telechat review on draft-ietf-pim-msdp-yang by Security Area Directorate Team Will not Review Version
    # In [107]: for a in ReviewAssignment.objects.filter(review__name__contains='review-ietf-pim-msdp-yang').order_by('review__name'):
    #      ...:     print (a)
    # Assignment for Reshad Rahman (Completed) : yangdoctors Early of draft-ietf-pim-msdp-yang
    # Assignment for Yingzhen Qu (Completed) : rtgdir Last Call of draft-ietf-pim-msdp-yang
    # Assignment for Reshad Rahman (Completed) : yangdoctors Last Call of draft-ietf-pim-msdp-yang
    # In [105]: for d in Document.objects.filter(name__contains='review-ietf-pim-msdp-yang').order_by('name'):
    #      ...:     print(d.name, d.time)
    # review-ietf-pim-msdp-yang-01-yangdoctors-early-rahman-2018-01-12 2020-02-12 15:00:06
    # review-ietf-pim-msdp-yang-08-rtgdir-lc-qu-2020-01-20 2020-01-20 15:00:00
    # review-ietf-pim-msdp-yang-12-secdir-lc-roca-2020-01-29 2020-01-29 00:18:10
    # review-ietf-pim-msdp-yang-12-yangdoctors-lc-rahman-2020-01-28 2020-01-28 19:05:44
    # review-ietf-pim-msdp-yang-16-yangdoctors-lc-rahman-2020-03-20 2020-03-20 06:16:25
    # But
    # In [113]: for a in ReviewAssignment.objects.filter(review_request__doc__name='draft-ietf-pim-msdp-yang'):
    #      ...:     print(a)
    # Assignment for Reshad Rahman (Completed) : yangdoctors Early of draft-ietf-pim-msdp-yang
    # Assignment for Reshad Rahman (Completed) : yangdoctors Last Call of draft-ietf-pim-msdp-yang
    # Assignment for Yingzhen Qu (Completed) : rtgdir Last Call of draft-ietf-pim-msdp-yang
    # Assignment for Meral Shirazipour (No Response) : genart Last Call of draft-ietf-pim-msdp-yang
    # Assignment for Vincent Roca (No Response) : secdir Last Call of draft-ietf-pim-msdp-yang
    # Assignment for Shwetha Bhandari (Accepted) : opsdir Last Call of draft-ietf-pim-msdp-yang
    # So, the secdir assignment that exists needs to have the review added and its state changed.
    a = ReviewAssignment.objects.get(review_request__doc__name='draft-ietf-pim-msdp-yang',review_request__type_id='lc',reviewer__person__name="Vincent Roca")
    r = Document.objects.get(name='review-ietf-pim-msdp-yang-12-secdir-lc-roca-2020-01-29')
    a.review = r
    a.state_id = 'completed'
    a.completed_on = r.time
    a.reviewed_rev = '12'
    a.save()
    # A new ReviewAssignment needs to be added to point to the yangdoctor review of -12
    a16 = ReviewAssignment.objects.get(review__name='review-ietf-pim-msdp-yang-16-yangdoctors-lc-rahman-2020-03-20')
    r12 = Document.objects.get(name='review-ietf-pim-msdp-yang-12-yangdoctors-lc-rahman-2020-01-28')
    ReviewAssignment.objects.create(
        review_request = a16.review_request,
        state_id = 'completed',
        reviewer = a16.reviewer,
        # Intentionally not making up assigned_on
        completed_on = r12.time,
        review = r12,
        reviewed_rev = '12',
        result_id = 'ready-issues',
        mailarch_url = r12.external_url,
    )
    # The secdir review request state is not the best, but it's not worth changing that history.
    # Intentionally not changing the state of the opsdir assignment
    # No suggestions to delete anything here.
    helper.add_comment('draft-ietf-pim-msdp-yang', 'Reconnected secdir lc review and changed assignment state to completed. Reconnected yangdoctors review of -12.')

    # review-ietf-spring-srv6-network-programming-17-opsdir-lc-romascanu-2020-08-20 2020-08-20 02:43:08
    # review-ietf-spring-srv6-network-programming-17-opsdir-lc-romascanu-2020-08-20-2 2020-08-20 02:43:08 
    # Assignment currently points to -2. Another double-submit. Resolve as above.
    a = ReviewAssignment.objects.get(review__name='review-ietf-spring-srv6-network-programming-17-opsdir-lc-romascanu-2020-08-20-2')
    a.review = Document.objects.get(name='review-ietf-spring-srv6-network-programming-17-opsdir-lc-romascanu-2020-08-20')
    a.save()
    Document.objects.filter(name='review-ietf-spring-srv6-network-programming-17-opsdir-lc-romascanu-2020-08-20-2').delete()
    helper.remove_file('review-ietf-spring-srv6-network-programming-17-opsdir-lc-romascanu-2020-08-20-2')
    helper.add_comment('draft-ietf-spring-srv6-network-programming','Removed unintended duplicate opsdir lc review')

    # In [116]: ReviewAssignment.objects.filter(review__name__contains='review-ietf-stir-passport-divert-07-
    #      ...: opsdir').values_list('review__name',flat=True)
    # Out[116]: <QuerySet ['review-ietf-stir-passport-divert-07-opsdir-lc-dunbar-2019-12-02-2']>
    # In [117]: for d in Document.objects.filter(name__contains='review-ietf-stir-passport-divert-07-opsdir').order_by('name'):
    #      ...:     print(d.name, d.time)
    # review-ietf-stir-passport-divert-07-opsdir-lc-dunbar-2019-12-02 2019-12-02 14:59:57
    # review-ietf-stir-passport-divert-07-opsdir-lc-dunbar-2019-12-02-2 2019-12-02 14:59:57
    # Another double-submit. Same treatment as above.
    a = ReviewAssignment.objects.get(review__name='review-ietf-stir-passport-divert-07-opsdir-lc-dunbar-2019-12-02-2')
    a.review = Document.objects.get(name='review-ietf-stir-passport-divert-07-opsdir-lc-dunbar-2019-12-02')
    a.save()
    Document.objects.filter(name='review-ietf-stir-passport-divert-07-opsdir-lc-dunbar-2019-12-02-2').delete()
    helper.remove_file('review-ietf-stir-passport-divert-07-opsdir-lc-dunbar-2019-12-02-2')
    helper.add_comment('draft-ietf-stir-passport-divert','Removed unintended duplicate opsdir lc review')

    # After the above...
    # In [57]: for d in Document.objects.filter(type_id='review',reviewassignment__isnull=True):
    #     ...:     print (d)
    # review-ietf-dots-architecture-15-tsvart-lc-tuexen-2020-01-27
    # There are no files on disk matching that and nothing references it. 
    Document.objects.filter(name='review-ietf-dots-architecture-15-tsvart-lc-tuexen-2020-01-27').delete()

def reverse(apps, schema_editor):
    # There is no point in trying to return to the broken objects
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('review', '0024_auto_20200520_0017'),
        ('doc','0036_orgs_vs_repos'),
        ('person','0016_auto_20200807_0750'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
