# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys
from tqdm import tqdm

from django.db import migrations

def fix_buggy_author_foreignkey(apps, schema_editor):
    DocumentAuthor = apps.get_model("doc", "DocumentAuthor")
    # apparently, we have a buggy key in the DB, fix it
    DocumentAuthor.objects.filter(author="[<Email: d3e3e3@gmail.com>]").update(author="d3e3e3@gmail.com")

def save_all_documents_in_history(apps, schema_editor):
    State = apps.get_model("doc", "State")
    Document = apps.get_model("doc", "Document")
    DocHistory = apps.get_model("doc", "DocHistory")
    RelatedDocument = apps.get_model("doc", "RelatedDocument")
    RelatedDocHistory = apps.get_model("doc", "RelatedDocHistory")
    DocumentAuthor = apps.get_model("doc", "DocumentAuthor")
    DocHistoryAuthor = apps.get_model("doc", "DocHistoryAuthor")

    sys.stderr.write('\n'
                    '    Ensuring that all documents have document history entries.\n'
                    '    This could take as much as an hour to run.\n')

    def canonical_name(self):
        name = self.name
        state = State.objects.filter(document=self, type_id=self.type_id).first()
        if self.type_id == "draft" and state.slug == "rfc":
            a = self.docalias_set.filter(name__startswith="rfc")
            if a:
                name = a[0].name
        elif self.type_id == "charter":
            try:
                return charter_name_for_group(self.chartered_group)
            except Exception as e:
                print("Exception: %s" % e)
                print("Document:  %s" % name)
        return name

    def charter_name_for_group(group):
        if group.type_id == "rg":
            top_org = "irtf"
        else:
            top_org = "ietf"

        return "charter-%s-%s" % (top_org, group.acronym)

    def save_document_in_history(doc):
        """Save a snapshot of document and related objects in the database."""


        def get_model_fields_as_dict(obj):
            return dict((field.name, getattr(obj, field.name))
                        for field in obj._meta.fields
                        if field is not obj._meta.pk)

        # copy fields
        fields = get_model_fields_as_dict(doc)
        fields["doc"] = doc
        fields["name"] = canonical_name(doc)

        objs = DocHistory.objects.filter(**fields)
        if objs.exists():
            try:
                dochist = objs.get(**fields)
            except DocHistory.MultipleObjectsReturned:
                dochist_list = list(objs)
                for dochist in dochist_list[1:]:
                    dochist.delete()
                dochist = dochist_list[0]
        else:
            dochist = DocHistory(**fields)
            dochist.save()

        # copy many to many
        for field in doc._meta.many_to_many:
            if field.rel.through and field.rel.through._meta.auto_created:
                setattr(dochist, field.name, getattr(doc, field.name).all())

        # copy remaining tricky many to many
        def transfer_fields(obj, HistModel):
            mfields = get_model_fields_as_dict(item)
            # map doc -> dochist
            for k, v in mfields.iteritems():
                if v == doc:
                    mfields[k] = dochist
            HistModel.objects.create(**mfields)

        for item in RelatedDocument.objects.filter(source=doc):
            transfer_fields(item, RelatedDocHistory)

        for item in DocumentAuthor.objects.filter(document=doc):
            transfer_fields(item, DocHistoryAuthor)

        return dochist

    from django.conf import settings
    settings.DEBUG = False # prevent out-of-memory problems

    docs = Document.objects.all()
    for d in tqdm(docs):
        save_document_in_history(d)

def noop_backward(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0012_auto_20160207_0537'),
        ('group', '0009_auto_20150930_0758'),
    ]

    operations = [
        migrations.RunPython(fix_buggy_author_foreignkey, noop_backward),
        migrations.RunPython(save_all_documents_in_history, noop_backward)
    ]
