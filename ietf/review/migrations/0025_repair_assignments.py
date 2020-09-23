# Copyright The IETF Trust 2020 All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    ReviewAssignment = apps.get_model('review','ReviewAssignment')
    Document = apps.get_model('doc','Document')


    # TODO: Add some DocEvents recording that changes were made, and why, to the history of each affected reviewed document.

    # review-allan-5g-fmc-encapsulation-04-tsvart-lc-black is a double-submit
    # In [120]: for d in Document.objects.filter(name__contains='review-allan-5g-fmc-encapsulation-04-tsvart
    #      ...: ').order_by('name'):
    #      ...:     print(d.name, d.time)
    #      ...:
    # review-allan-5g-fmc-encapsulation-04-tsvart-lc-black-2020-06-30 2020-06-30 11:06:30
    # review-allan-5g-fmc-encapsulation-04-tsvart-lc-black-2020-06-30-2 2020-06-30 11:06:30
    # (I've put some more detail below on this as my understanding of double-submit improved)
    # The recommendation is to point the reviewassignment at the first submission, and delete the -2.
    a = ReviewAssignment.objects.get(review_request__doc__name='draft-allan-5g-fmc-encapsulation', review_request__team__acronym='tsvart')
    a.review = Document.objects.get(name='review-allan-5g-fmc-encapsulation-04-tsvart-lc-black-2020-06-30')
    a.save()

    # Document.objects.filter(name='review-allan-5g-fmc-encapsulation-04-tsvart-lc-black-2020-06-30-2').delete()
    # (11,
    #  {'community.CommunityList_added_docs': 0,
    #   'community.SearchRule_name_contains_index': 0,
    #   'doc.RelatedDocument': 0,
    #   'doc.DocumentAuthor': 1,
    #   'doc.Document_states': 1,
    #   'doc.Document_tags': 0,
    #   'doc.Document_formal_languages': 0,
    #   'doc.DocumentURL': 0,
    #   'doc.DocExtResource': 0,
    #   'doc.RelatedDocHistory': 0,
    #   'doc.DocHistoryAuthor': 1,
    #   'doc.DocHistory_states': 2,
    #   'doc.DocHistory_tags': 0,
    #   'doc.DocHistory_formal_languages': 0,
    #   'doc.DocAlias_docs': 1,
    #   'doc.DocReminder': 0,
    #   'group.GroupMilestone_docs': 0,
    #   'group.GroupMilestoneHistory_docs': 0,
    #   'liaisons.LiaisonStatementAttachment': 0,
    #   'meeting.SessionPresentation': 0,
    #   'message.Message_related_docs': 0,
    #   'review.ReviewWish': 0,
    #   'doc.DocHistory': 2,
    #   'doc.NewRevisionDocEvent': 1,
    #   'doc.DocEvent': 1,
    #   'doc.Document': 1})

    # TODO: Remove the -2 from disk?


    # This one is just simply disconnected. No duplicates or anything to remove.
    a = ReviewAssignment.objects.get(review_request__doc__name='draft-ietf-6lo-minimal-fragment',review_request__team__acronym='opsdir')
    a.review = Document.objects.get(name='review-ietf-6lo-minimal-fragment-09-opsdir-lc-banks-2020-01-31')
    a.save()

    # This review took place when we were spinning up the review tool. I suspect there were bugs at the time that we no longer have insight into.
    # These two do not exist on disk
    # review-ietf-6lo-privacy-considerations-04-secdir-lc-kaduk-2016-11-30
    # review-ietf-6lo-privacy-considerations-04-secdir-lc-kaduk-2016-11-30-2
    # These are identical except for 0d0a vs 0a and newline at end of file
    # review-ietf-6lo-privacy-considerations-04-secdir-lc-kaduk-2016-11-30-3
    # review-ietf-6lo-privacy-considerations-04-secdir-lc-kaduk-2016-12-01
    # -12-01 is already reachable from the assignment. I suggest:
    # Document.objects.filter(name__startswith='review-ietf-6lo-privacy-considerations-04-secdir-lc-kaduk-2016-11-30').delete()
    # (21,
    #  {'community.CommunityList_added_docs': 0,
    #   'community.SearchRule_name_contains_index': 0,
    #   'doc.RelatedDocument': 0,
    #   'doc.DocumentAuthor': 0,
    #   'doc.Document_states': 3,
    #   'doc.Document_tags': 0,
    #   'doc.Document_formal_languages': 0,
    #   'doc.DocumentURL': 0,
    #   'doc.DocExtResource': 0,
    #   'doc.RelatedDocHistory': 0,
    #   'doc.DocHistoryAuthor': 0,
    #   'doc.DocHistory_states': 3,
    #   'doc.DocHistory_tags': 0,
    #   'doc.DocHistory_formal_languages': 0,
    #   'doc.DocAlias_docs': 3,
    #   'doc.DocReminder': 0,
    #   'group.GroupMilestone_docs': 0,
    #   'group.GroupMilestoneHistory_docs': 0,
    #   'liaisons.LiaisonStatementAttachment': 0,
    #   'meeting.SessionPresentation': 0,
    #   'message.Message_related_docs': 0,
    #   'review.ReviewWish': 0,
    #   'doc.DocHistory': 3,
    #   'doc.NewRevisionDocEvent': 3,
    #   'doc.DocEvent': 3,
    #   'doc.Document': 3})

    a = ReviewAssignment.objects.get(review_request__doc__name='draft-ietf-bess-nsh-bgp-control-plane',review_request__team__acronym='rtgdir',reviewer__person__name__icontains='singh')
    a.review = Document.objects.get(name='review-ietf-bess-nsh-bgp-control-plane-13-rtgdir-lc-singh-2020-01-29')
    a.state_id = 'completed'
    a.reviewed_rev='13'
    a.save()

    # In [121]: for d in Document.objects.filter(name__contains='review-ietf-capport-architecture-08-genart-
    #      ...: lc-halpern').order_by('name'):
    #      ...:     print(d.name, d.time)
    #      ...:
    # review-ietf-capport-architecture-08-genart-lc-halpern-2020-05-16 2020-05-16 15:34:35
    # review-ietf-capport-architecture-08-genart-lc-halpern-2020-05-16-2 2020-05-16 15:35:55
    # Not the same as the other double-submits, but likely a failure on the first submit midway through processing that led to the second.
    # rjsparks@ietfa:/a/www/ietf-ftp/review> ls review-ietf-capport-architecture-08-genart-lc-halpern*
    # review-ietf-capport-architecture-08-genart-lc-halpern-2020-05-16-2.txt
    # Only -2 exists on disk
    # -2 is what is currently pointed to by the review assignment.
    # We could delete -05-16, and leave -05-16-2 as an anomoly. (-05-16 would 404)
    # Or we could replace -05-16 with the content of -2 and remove -2.
    # If we did the latter, any external references to -05-16-2 would break, but I'm reticent to start down the path of putting something sensical there. 
    # Right now, any review document not pointed to by a reviewassignment is a database error, and the view code assumes it won't. We can make it more robust against crashing, but I don't think we should try to adapt the models to model the corruption.

    # Opsdir last call review of draft-ietf-cbor-array-tags-07
    # Got sent to the opsdir list (which is closed) twice - no resulting thread from either
    # rjsparks@ietfa:/a/www/ietf-ftp/review> ls review-ietf-cbor-array-tags-07-opsdir-lc-dunbar*
    # review-ietf-cbor-array-tags-07-opsdir-lc-dunbar-2019-08-26-2.txt
    # review-ietf-cbor-array-tags-07-opsdir-lc-dunbar-2019-08-26.txt
    # In [122]: for d in Document.objects.filter(name__contains='review-ietf-cbor-array-tags-07-opsdir-lc-du
    #      ...: nbar').order_by('name'):
    #      ...:     print(d.name, d.time)
    #      ...:
    # review-ietf-cbor-array-tags-07-opsdir-lc-dunbar-2019-08-26 2019-08-26 14:13:29
    # review-ietf-cbor-array-tags-07-opsdir-lc-dunbar-2019-08-26-2 2019-08-26 14:13:29
    # This is a double-submit.
    # Right now, the ReviewAssignment points to 08-26. Suggest we:
    # Document.objects.filter(name='review-ietf-cbor-array-tags-07-opsdir-lc-dunbar-2019-08-26-2').delete()
    # (12,
    #  {'community.CommunityList_added_docs': 0,
    #   'community.SearchRule_name_contains_index': 1,
    #   'doc.RelatedDocument': 0,
    #   'doc.DocumentAuthor': 1,
    #   'doc.Document_states': 1,
    #   'doc.Document_tags': 0,
    #   'doc.Document_formal_languages': 0,
    #   'doc.DocumentURL': 0,
    #   'doc.DocExtResource': 0,
    #   'doc.RelatedDocHistory': 0,
    #   'doc.DocHistoryAuthor': 1,
    #   'doc.DocHistory_states': 2,
    #   'doc.DocHistory_tags': 0,
    #   'doc.DocHistory_formal_languages': 0,
    #   'doc.DocAlias_docs': 1,
    #   'doc.DocReminder': 0,
    #   'group.GroupMilestone_docs': 0,
    #   'group.GroupMilestoneHistory_docs': 0,
    #   'liaisons.LiaisonStatementAttachment': 0,
    #   'meeting.SessionPresentation': 0,
    #   'message.Message_related_docs': 0,
    #   'review.ReviewWish': 0,
    #   'doc.DocHistory': 2,
    #   'doc.NewRevisionDocEvent': 1,
    #   'doc.DocEvent': 1,
    #   'doc.Document': 1})

    # In [73]: for d in Document.objects.filter(name__startswith='review-ietf-detnet-m
    #     ...: pls-over-udp-ip'):
    #     ...:     print(d.name, d.time)
    #     ...:
    # <snip/>
    # review-ietf-detnet-mpls-over-udp-ip-06-genart-lc-holmberg-2020-09-01 2020-09-01 13:47:55
    # review-ietf-detnet-mpls-over-udp-ip-06-genart-lc-holmberg-2020-09-01-2 2020-09-01 13:47:55
    # review-ietf-detnet-mpls-over-udp-ip-06-opsdir-lc-romascanu-2020-09-03 2020-09-03 02:49:33
    # review-ietf-detnet-mpls-over-udp-ip-06-opsdir-lc-romascanu-2020-09-03-2 2020-09-03 02:49:33
    # <snip/>
    # Both of those are places where the submit button got hit twice in rapid successsion.
    # Messages went to the list twice. No threads were started
    # The review assignments currently point to the -2 versions. I think we change them to point to the not -2 versions and delete the -2 version documents.

    # This draft had a contentious last call (not because of this review)
    # rjsparks@ietfa:/a/www/ietf-ftp/review> ls -l review-ietf-dprive-rfc7626-bis-03-genart*
    # -rw-r--r-- 1 wwwrun www 1087 Dec  4  2019 review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04-2.txt
    # -rw-r--r-- 1 wwwrun www 1087 Dec  4  2019 review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04-3.txt
    # -rw-r--r-- 1 wwwrun www 1087 Dec  4  2019 review-ietf-dprive-rfc7626-bis-03-genart-lc-shirazipour-2019-12-04.txt
    # These files are identical.
    # In [75]: Document.objects.filter(name__startswith='review-ietf-dprive-rfc7626-bi
    #     ...: s-03-genart-lc-shirazipour-2019-12-04').values_list('time',flat=True)
    # Out[75]: <QuerySet [datetime.datetime(2019, 12, 4, 13, 40, 30), datetime.datetime(2019, 12, 4, 13, 40, 30), datetime.datetime(2019, 12, 4, 13, 40, 32)]>
    # So again, the submit button got hit several times in rapid succession
    # Interestingly, this was a case where the review was sent to the list first and then Meral told the datatracker about it, so it's only on the list(s) once.
    # I think we change the assingment to point to 12-04 and delete -2 and -3.

    # In [76]: Document.objects.filter(name__startswith='review-ietf-emu-rfc5448bis-06
    #     ...: -secdir-lc-rose')
    # Out[76]: <QuerySet [<Document: review-ietf-emu-rfc5448bis-06-secdir-lc-rose-2020-01-27>, <Document: review-ietf-emu-rfc5448bis-06-secdir-lc-rose-2020-02-06>]>
    # rjsparks@ietfa:/a/www/ietf-ftp/review> ls review-ietf-emu-rfc5448bis-06-secdir-lc-rose*
    # review-ietf-emu-rfc5448bis-06-secdir-lc-rose-2020-02-06.txt
    # review assignment points to 02-06.
    # Suggest we delete -01-27

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

    # In [81]: Document.objects.filter(name__startswith='review-ietf-mpls-spl-terminol
    #     ...: ogy-03-opsdir-lc-jaeggli').values_list('time',flat=True)
    # Out[81]: <QuerySet [datetime.datetime(2020, 8, 15, 16, 38, 37), datetime.datetime(2020, 8, 15, 16, 38, 37)]>
    # Another double-submit.
    # The review assignment already points to -08-15. Suggest we delete -08-15-2


    # In [82]: Document.objects.filter(name__startswith='review-ietf-netconf-subscribe
    #     ...: d-notifications-23-rtgdir').values_list('time',flat=True)
    # Out[82]: <QuerySet [datetime.datetime(2019, 4, 16, 3, 45, 4), datetime.datetime(2019, 4, 16, 3, 45, 6)]>
    # Another double-submit. This time the second won and the review assignments points to -2. I suggest we change it to point to the base and delete -2.


    # In [84]: Document.objects.filter(name__contains='ietf-netconf-yang-push-22-genar
    #     ...: t-lc-bryant').values_list('time',flat=True)
    # Out[84]: <QuerySet [datetime.datetime(2019, 4, 10, 13, 40, 41), datetime.datetime(2019, 4, 10, 13, 40, 41)]>
    # In [85]: ReviewAssignment.objects.get(review__name__contains='ietf-netconf-yang-
    #     ...: push-22-genart-lc-bryant').review
    # Out[85]: <Document: review-ietf-netconf-yang-push-22-genart-lc-bryant-2019-04-10-2>
    # Same as above.


    # In [92]: for d in Document.objects.filter(name__contains='ietf-nfsv4-rpcrdma-cm-pvt-data-06').order_by
    #     ...: ('name'):
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

    # In [101]: ReviewAssignment.objects.filter(review__name__contains='review-ietf-pce-pcep-flowspec-09-tsv
    #      ...: art').values_list('review__name',flat=True)
    # Out[101]: <QuerySet ['review-ietf-pce-pcep-flowspec-09-tsvart-lc-touch-2020-07-03-2']>
    # In [102]: for d in Document.objects.filter(name__contains='review-ietf-pce-pcep-flowspec-09-tsvart').o
    #      ...: rder_by('name'):
    #      ...:     print(d.name, d.time)
    #      ...:
    # review-ietf-pce-pcep-flowspec-09-tsvart-lc-touch-2020-07-03 2020-07-03 19:20:49
    # review-ietf-pce-pcep-flowspec-09-tsvart-lc-touch-2020-07-03-2 2020-07-03 19:20:49
    # Same as double-submits above. 

    # draft-ietf-pim-msdp-yang history will be a bit more complicated to straighten out.
    # It is currently in AUTH48...
    # There is a combination of secretaries trying to route around the confusion and a reviewer accidentally updating the wrong review.
    # Everything went to lists.
    # In [110]: for rq in ReviewRequest.objects.filter(doc__name__contains='ietf-pim-msdp-yang'):
    #      ...:     print(rq)
    #      ...:
    # Early review on draft-ietf-pim-msdp-yang by YANG Doctors Assigned
    # Last Call review on draft-ietf-pim-msdp-yang by YANG Doctors Assigned
    # Last Call review on draft-ietf-pim-msdp-yang by Routing Area Directorate Assigned
    # Last Call review on draft-ietf-pim-msdp-yang by General Area Review Team (Gen-ART) Overtaken by Events
    # Last Call review on draft-ietf-pim-msdp-yang by Security Area Directorate Overtaken by Events
    # Last Call review on draft-ietf-pim-msdp-yang by Ops Directorate Assigned
    # Last Call review on draft-ietf-pim-msdp-yang by Transport Area Review Team Team Will not Review Document
    # Telechat review on draft-ietf-pim-msdp-yang by Security Area Directorate Team Will not Review Version
    # In [107]: for a in ReviewAssignment.objects.filter(review__name__contains='review-ietf-pim-msdp-yang')
    #      ...: .order_by('review__name'):
    #      ...:     print (a)
    #      ...:
    # Assignment for Reshad Rahman (Completed) : yangdoctors Early of draft-ietf-pim-msdp-yang
    # Assignment for Yingzhen Qu (Completed) : rtgdir Last Call of draft-ietf-pim-msdp-yang
    # Assignment for Reshad Rahman (Completed) : yangdoctors Last Call of draft-ietf-pim-msdp-yang
    # In [105]: for d in Document.objects.filter(name__contains='review-ietf-pim-msdp-yang').order_by('name'
    #      ...: ):
    #      ...:     print(d.name, d.time)
    #      ...:
    # But
    # In [113]: for a in ReviewAssignment.objects.filter(review_request__doc__name='draft-ietf-pim-msdp-yang
    #      ...: '):
    #      ...:     print(a)
    #      ...:
    # Assignment for Reshad Rahman (Completed) : yangdoctors Early of draft-ietf-pim-msdp-yang
    # Assignment for Reshad Rahman (Completed) : yangdoctors Last Call of draft-ietf-pim-msdp-yang
    # Assignment for Yingzhen Qu (Completed) : rtgdir Last Call of draft-ietf-pim-msdp-yang
    # Assignment for Meral Shirazipour (No Response) : genart Last Call of draft-ietf-pim-msdp-yang
    # Assignment for Vincent Roca (No Response) : secdir Last Call of draft-ietf-pim-msdp-yang
    # Assignment for Shwetha Bhandari (Accepted) : opsdir Last Call of draft-ietf-pim-msdp-yang
    # review-ietf-pim-msdp-yang-01-yangdoctors-early-rahman-2018-01-12 2020-02-12 15:00:06
    # review-ietf-pim-msdp-yang-08-rtgdir-lc-qu-2020-01-20 2020-01-20 15:00:00
    # review-ietf-pim-msdp-yang-12-secdir-lc-roca-2020-01-29 2020-01-29 00:18:10
    # review-ietf-pim-msdp-yang-12-yangdoctors-lc-rahman-2020-01-28 2020-01-28 19:05:44
    # review-ietf-pim-msdp-yang-16-yangdoctors-lc-rahman-2020-03-20 2020-03-20 06:16:25
    # So, the secdir assignment that exists needs to have the review added and its state changed.
    # The yangdoctor's assingment just needs to point to the completed review?
    # The requests need state tweaks
    # No suggestions to delete anything here.

    # review-ietf-spring-srv6-network-programming-17-opsdir-lc-romascanu-2020-08-20 2020-08-20 02:43:08
    # review-ietf-spring-srv6-network-programming-17-opsdir-lc-romascanu-2020-08-20-2 2020-08-20 02:43:08 
    # Assignment currently points to -2. Another double-submit. Resolve as above.

    # In [116]: ReviewAssignment.objects.filter(review__name__contains='review-ietf-stir-passport-divert-07-
    #      ...: opsdir').values_list('review__name',flat=True)
    # Out[116]: <QuerySet ['review-ietf-stir-passport-divert-07-opsdir-lc-dunbar-2019-12-02-2']>

    # In [117]: for d in Document.objects.filter(name__contains='review-ietf-stir-passport-divert-07-opsdir'
    #      ...: ).order_by('name'):
    #      ...:     print(d.name, d.time)
    #      ...:
    # review-ietf-stir-passport-divert-07-opsdir-lc-dunbar-2019-12-02 2019-12-02 14:59:57
    # review-ietf-stir-passport-divert-07-opsdir-lc-dunbar-2019-12-02-2 2019-12-02 14:59:57
    # Another double-submit. Same treatment as above.


    # TODO: write a migration that repairs any remaining mailarchive urls that have b'<>' segments. There are currently 4, but the above suggestions would remove 2.

def reverse(apps, schema_editor):
    # There is no point in trying to return to the broken objects
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('review', '0024_auto_20200520_0017'),
        ('doc','0036_orgs_vs_repos'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
