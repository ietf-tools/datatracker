import json

from django.utils.html import escape
from django import forms
from django.core.urlresolvers import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, DocAlias

def tokeninput_id_doc_name_json(objs):
    return json.dumps([{ "id": o.pk, "name": escape(o.name) } for o in objs])

class AutocompletedDocumentsField(forms.CharField):
    """Tokenizing autocompleted multi-select field for choosing
    documents using jquery.tokeninput.js.

    The field uses a comma-separated list of primary keys in a
    CharField element as its API, the tokeninput Javascript adds some
    selection magic on top of this so we have to pass it a JSON
    representation of ids and user-understandable labels."""

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

        super(AutocompletedDocumentsField, self).__init__(*args, **kwargs)

        self.widget.attrs["class"] = "tokenized-field"
        self.widget.attrs["data-hint-text"] = hint_text
        if self.max_entries != None:
            self.widget.attrs["data-max-entries"] = self.max_entries

    def parse_tokenized_value(self, value):
        return [x.strip() for x in value.split(",") if x.strip()]

    def prepare_value(self, value):
        if not value:
            value = ""
        if isinstance(value, basestring):
            pks = self.parse_tokenized_value(value)
            value = self.model.objects.filter(pk__in=pks, type=self.doc_type)
        if isinstance(value, self.model):
            value = [value]

        self.widget.attrs["data-pre"] = tokeninput_id_doc_name_json(value)

        # doing this in the constructor is difficult because the URL
        # patterns may not have been fully constructed there yet
        self.widget.attrs["data-ajax-url"] = urlreverse("ajax_tokeninput_search_docs", kwargs={
            "doc_type": self.doc_type,
            "model_name": self.model.__name__.lower()
        })

        return ",".join(o.pk for o in value)

    def clean(self, value):
        value = super(AutocompletedDocumentsField, self).clean(value)
        pks = self.parse_tokenized_value(value)

        objs = self.model.objects.filter(pk__in=pks)

        found_pks = [str(o.pk) for o in objs]
        failed_pks = [x for x in pks if x not in found_pks]
        if failed_pks:
            raise forms.ValidationError(u"Could not recognize the following documents: {pks}. You can only input documents already registered in the Datatracker.".format(pks=", ".join(failed_pks)))

        if self.max_entries != None and len(objs) > self.max_entries:
            raise forms.ValidationError(u"You can select at most %s entries only." % self.max_entries)

        return objs

class AutocompletedDocAliasField(AutocompletedDocumentsField):
    def __init__(self, model=DocAlias, *args, **kwargs):
        super(AutocompletedDocAliasField, self).__init__(model=model, *args, **kwargs)
    
