# Copyright The IETF Trust 2024, All Rights Reserved

from django.db import migrations


def get_helper(DocHistory, RelatedDocument, RelatedDocHistory, DocumentAuthor, DocHistoryAuthor):
    """Dependency injection wrapper"""

    def save_document_in_history(doc):
        """Save a snapshot of document and related objects in the database.
        
        Local copy of ietf.doc.utils.save_document_in_history() to avoid depending on the
        code base in a migration.
        """
    
        def get_model_fields_as_dict(obj):
            return dict((field.name, getattr(obj, field.name))
                        for field in obj._meta.fields
                        if field is not obj._meta.pk)
    
        # copy fields
        fields = get_model_fields_as_dict(doc)
        fields["doc"] = doc
        fields["name"] = doc.name
    
        dochist = DocHistory(**fields)
        dochist.save()
    
        # copy many to many
        for field in doc._meta.many_to_many:
            if field.remote_field.through and field.remote_field.through._meta.auto_created:
                hist_field = getattr(dochist, field.name)
                hist_field.clear()
                hist_field.set(getattr(doc, field.name).all())
    
        # copy remaining tricky many to many
        def transfer_fields(obj, HistModel):
            mfields = get_model_fields_as_dict(item)
            # map doc -> dochist
            for k, v in mfields.items():
                if v == doc:
                    mfields[k] = dochist
            HistModel.objects.create(**mfields)
    
        for item in RelatedDocument.objects.filter(source=doc):
            transfer_fields(item, RelatedDocHistory)
    
        for item in DocumentAuthor.objects.filter(document=doc):
            transfer_fields(item, DocHistoryAuthor)
    
        return dochist
    
    return save_document_in_history


def forward(apps, schema_editor):
    """Mark watching draft-iesg state unused after removing it from Documents"""
    StateDocEvent = apps.get_model("doc", "StateDocEvent")
    Document = apps.get_model("doc", "Document")
    State = apps.get_model("doc", "State")
    StateType = apps.get_model("doc", "StateType")
    Person = apps.get_model("person", "Person")
    
    save_document_in_history = get_helper(
        DocHistory=apps.get_model("doc", "DocHistory"),
        RelatedDocument=apps.get_model("doc", "RelatedDocument"),
        RelatedDocHistory=apps.get_model("doc", "RelatedDocHistory"),
        DocumentAuthor=apps.get_model("doc", "DocumentAuthor"),
        DocHistoryAuthor=apps.get_model("doc", "DocHistoryAuthor"),
    )

    draft_iesg_state_type = StateType.objects.get(slug="draft-iesg")
    idexists_state = State.objects.get(type=draft_iesg_state_type, slug="idexists")
    watching_state = State.objects.get(type=draft_iesg_state_type, slug="watching")
    system_person = Person.objects.get(name="(System)")

    # Remove state from documents that currently have it
    for doc in Document.objects.filter(states=watching_state):
        assert doc.type_id == "draft"
        doc.states.remove(watching_state)
        doc.states.add(idexists_state)
        e = StateDocEvent.objects.create(
            type="changed_state",
            by=system_person,
            doc=doc,
            rev=doc.rev,
            desc=f"{draft_iesg_state_type.label} changed to <b>{idexists_state.name}</b> from {watching_state.name}",
            state_type=draft_iesg_state_type,
            state=idexists_state,
        )
        doc.time = e.time
        doc.save()
        save_document_in_history(doc)
    assert not Document.objects.filter(states=watching_state).exists()

    # Mark state as unused
    watching_state.used = False
    watching_state.save()


def reverse(apps, schema_editor):
    """Mark watching draft-iesg state as used
    
    Does not try to re-apply the state to Documents modified by the forward migration. This
    could be done in theory, but would either require dangerous history rewriting or add a
    lot of history junk.
    """
    State = apps.get_model("doc", "State")
    StateType = apps.get_model("doc", "StateType")
    State.objects.filter(
        type=StateType.objects.get(slug="draft-iesg"), slug="watching"
    ).update(used=True)


class Migration(migrations.Migration):

    dependencies = [
        ("doc", "0023_bofreqspamstate"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
