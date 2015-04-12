import json

from django.utils.html import escape
from django import forms
from django.core.urlresolvers import reverse as urlreverse

from ietf.liaisons.models import LiaisonStatement

def select2_id_liaison_json(objs):
    return json.dumps([{ "id": o.pk, "text": escape(o.title) } for o in objs])

class SearchableLiaisonStatementField(forms.IntegerField):
    """Server-based multi-select field for choosing liaison statements using
    select2.js."""

    def __init__(self, hint_text="Type in title to search for document", *args, **kwargs):
        super(SearchableLiaisonStatementField, self).__init__(*args, **kwargs)

        self.widget.attrs["class"] = "select2-field"
        self.widget.attrs["data-placeholder"] = hint_text
        self.widget.attrs["data-max-entries"] = 1

    def prepare_value(self, value):
        if not value:
            value = None
        elif isinstance(value, LiaisonStatement):
            value = value
        else:
            value = LiaisonStatement.objects.exclude(approved=None).filter(pk=value).first()

        self.widget.attrs["data-pre"] = select2_id_liaison_json([value] if value else [])

        # doing this in the constructor is difficult because the URL
        # patterns may not have been fully constructed there yet
        self.widget.attrs["data-ajax-url"] = urlreverse("ajax_select2_search_liaison_statements")

        return value

    def clean(self, value):
        value = super(SearchableLiaisonStatementField, self).clean(value)

        if value == None:
            return None

        obj = LiaisonStatement.objects.filter(pk=value).first()
        if not obj and self.required:
            raise forms.ValidationError(u"You must select a value.")

        return obj

