import json

from django.utils.html import escape
from django import forms
from django.core.urlresolvers import reverse as urlreverse

from ietf.doc.models import Document, DocAlias
from ietf.doc.utils import uppercase_std_abbreviated_name

def select2_id_doc_name_json(objs):
    return json.dumps([{ "id": o.pk, "text": escape(uppercase_std_abbreviated_name(o.name)) } for o in objs])

# FIXME: select2 version 4 uses a standard select for the AJAX case -
# switching to that would allow us to derive from the standard
# multi-select machinery in Django instead of the manual CharField
# stuff below

class SearchableDocumentsField(forms.CharField):
    """Server-based multi-select field for choosing documents using
    select2.js.

    The field uses a comma-separated list of primary keys in a
    CharField element as its API with some extra attributes used by
    the Javascript part."""

    def __init__(self,
                 max_entries=None, # max number of selected objs
                 model=Document,
                 hint_text="Type in name to search for document",
                 doc_type="draft",
                 *args, **kwargs):
        kwargs["max_length"] = 10000
        self.max_entries = max_entries
        self.doc_type = doc_type
        self.model = model

        super(SearchableDocumentsField, self).__init__(*args, **kwargs)

        self.widget.attrs["class"] = "select2-field form-control"
        self.widget.attrs["data-placeholder"] = hint_text
        if self.max_entries != None:
            self.widget.attrs["data-max-entries"] = self.max_entries

    def parse_select2_value(self, value):
        return [x.strip() for x in value.split(",") if x.strip()]

    def prepare_value(self, value):
        if not value:
            value = ""
        if isinstance(value, (int, long)):
            value = str(value)
        if isinstance(value, basestring):
            pks = self.parse_select2_value(value)
            value = self.model.objects.filter(pk__in=pks)
            filter_args = {}
            if self.model == DocAlias:
                filter_args["document__type"] = self.doc_type
            else:
                filter_args["type"] = self.doc_type
            value = value.filter(**filter_args)
        if isinstance(value, self.model):
            value = [value]

        self.widget.attrs["data-pre"] = select2_id_doc_name_json(value)

        # doing this in the constructor is difficult because the URL
        # patterns may not have been fully constructed there yet
        self.widget.attrs["data-ajax-url"] = urlreverse("ajax_select2_search_docs", kwargs={
            "doc_type": self.doc_type,
            "model_name": self.model.__name__.lower()
        })

        return u",".join(unicode(o.pk) for o in value)

    def clean(self, value):
        value = super(SearchableDocumentsField, self).clean(value)
        pks = self.parse_select2_value(value)

        objs = self.model.objects.filter(pk__in=pks)

        found_pks = [str(o.pk) for o in objs]
        failed_pks = [x for x in pks if x not in found_pks]
        if failed_pks:
            raise forms.ValidationError(u"Could not recognize the following documents: {pks}. You can only input documents already registered in the Datatracker.".format(pks=", ".join(failed_pks)))

        if self.max_entries != None and len(objs) > self.max_entries:
            raise forms.ValidationError(u"You can select at most %s entries only." % self.max_entries)

        return objs

class SearchableDocumentField(SearchableDocumentsField):
    """Specialized to only return one Document."""
    def __init__(self, model=Document, *args, **kwargs):
        kwargs["max_entries"] = 1
        super(SearchableDocumentField, self).__init__(model=model, *args, **kwargs)

    def clean(self, value):
        return super(SearchableDocumentField, self).clean(value).first()
    
class SearchableDocAliasesField(SearchableDocumentsField):
    def __init__(self, model=DocAlias, *args, **kwargs):
        super(SearchableDocAliasesField, self).__init__(model=model, *args, **kwargs)
    
class SearchableDocAliasField(SearchableDocumentsField):
    """Specialized to only return one DocAlias."""
    def __init__(self, model=DocAlias, *args, **kwargs):
        kwargs["max_entries"] = 1
        super(SearchableDocAliasField, self).__init__(model=model, *args, **kwargs)

    def clean(self, value):
        return super(SearchableDocAliasField, self).clean(value).first()

    
