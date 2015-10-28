# -*- coding: utf-8 -*-
from __future__ import unicode_literals

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

    def canonical_name(self):
        name = self.name
        state = State.objects.filter(document=self, type_id=self.type_id).first()
        if self.type_id == "draft" and state.slug == "rfc":
            a = self.docalias_set.filter(name__startswith="rfc")
            if a:
                name = a[0].name
        elif self.type_id == "charter":
            return charter_name_for_group(self.chartered_group)
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

    for d in Document.objects.iterator():
        save_document_in_history(d)

class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0010_auto_20150930_0251'),
        ('group', '0007_auto_20150930_0758'),
    ]

    operations = [
        migrations.RunPython(fix_buggy_author_foreignkey),
        migrations.RunPython(save_all_documents_in_history)
    ]
