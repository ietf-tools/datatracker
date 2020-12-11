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

def forward(apps,schema_editor):
    Document = apps.get_model('doc','Document')
    Person = apps.get_model('person','Person')

    # The calculation of review_path makes the assumption that DOCUMENT_PATH_PATTERN only uses 
    # things that are invariant for review documents. For production, as of this commit, that's 
    # DOCUMENT_PATH_PATTERN = '/a/www/ietf-ftp/{doc.type_id}/'. There are plans to change that pattern
    # soon to '/a/ietfdata/doc/{doc.type_id}/'

    helper = Helper(
        review_path = settings.DOCUMENT_PATH_PATTERN.format(doc=Document.objects.filter(type_id='review').last()),
        comments_by = Person.objects.get(name='(System)'),
        document_class = Document,
    )

    # In [2]: for d in Document.objects.filter(name__startswith='review-ietf-capport-api-07-opsdir'):
    #    ...:     print(d.name,d.time)
    # review-ietf-capport-api-07-opsdir-lc-dunbar-2020-05-09 2020-05-09 14:59:40
    # review-ietf-capport-api-07-opsdir-lc-dunbar-2020-05-09-2 2020-05-09 15:06:44
    # This is similar to draft-ietf-capport-architecture-08-genart-lc-halpern...
    # Only -2 exists on disk.
    # But the Document for ...-2020-05-09 has not type or state - it was very incompletely set up - deleting it results in:
    # (3,
    #  {'community.CommunityList_added_docs': 0,
    #   'community.SearchRule_name_contains_index': 0,
    #   'doc.RelatedDocument': 0,
    #   'doc.DocumentAuthor': 0,
    #   'doc.Document_states': 0,
    #   'doc.Document_tags': 0,
    #   'doc.Document_formal_languages': 0,
    #   'doc.DocumentURL': 0,
    #   'doc.DocExtResource': 0,
    #   'doc.DocAlias_docs': 1,
    #   'doc.DocReminder': 0,
    #   'group.GroupMilestone_docs': 0,
    #   'group.GroupMilestoneHistory_docs': 0,
    #   'liaisons.LiaisonStatementAttachment': 0,
    #   'meeting.SessionPresentation': 0,
    #   'message.Message_related_docs': 0,
    #   'review.ReviewWish': 0,
    #   'doc.DocEvent': 1,
    #   'doc.Document': 1})
    # Repairing that back to remove the -2 will hide more information than simply removing the incompletely set up document object.
    # But the -2 document currently has no type (see #3145)
    Document.objects.get(name='review-ietf-capport-api-07-opsdir-lc-dunbar-2020-05-09').delete()
    review = Document.objects.get(name='review-ietf-capport-api-07-opsdir-lc-dunbar-2020-05-09-2')
    review.type_id='review'
    review.save()
    helper.add_comment('draft-ietf-capport-api','Removed an unintended duplicate version of the opsdir lc review')

def reverse(apps,schema_editor):
    # There is no point in returning to the broken version
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('review', '0025_repair_assignments'),
        ('doc','0039_auto_20201109_0439'),
        ('person','0018_auto_20201109_0439'),
    ]

    operations = [
            migrations.RunPython(forward, reverse),
    ]
