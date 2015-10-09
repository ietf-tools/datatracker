import json

from django.utils.html import escape
from django import forms
from django.core.urlresolvers import reverse as urlreverse

from ietf.liaisons.models import LiaisonStatement

def select2_id_liaison_json(objs):
    return json.dumps([{ "id": o.pk, "text":u"[{}] {}".format(o.pk, escape(o.title)) } for o in objs])

def select2_id_group_json(objs):
    return json.dumps([{ "id": o.pk, "text": escape(o.acronym) } for o in objs])

class SearchableLiaisonStatementsField(forms.CharField):
    """Server-based multi-select field for choosing liaison statements using
    select2.js."""

    def __init__(self,
                 max_entries = None,
                 hint_text="Type in title to search for document",
                 model = LiaisonStatement,
                 *args, **kwargs):
        kwargs["max_length"] = 10000
        self.model = model
        self.max_entries = max_entries

        super(SearchableLiaisonStatementsField, self).__init__(*args, **kwargs)

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
        if isinstance(value, LiaisonStatement):
            value = [value]

        self.widget.attrs["data-pre"] = select2_id_liaison_json(value)

        # doing this in the constructor is difficult because the URL
        # patterns may not have been fully constructed there yet
        self.widget.attrs["data-ajax-url"] = urlreverse("ietf.liaisons.views.ajax_select2_search_liaison_statements")

        return u",".join(unicode(o.pk) for o in value)

    def clean(self, value):
        value = super(SearchableLiaisonStatementsField, self).clean(value)
        pks = self.parse_select2_value(value)

        objs = self.model.objects.filter(pk__in=pks)

        found_pks = [str(o.pk) for o in objs]
        failed_pks = [x for x in pks if x not in found_pks]
        if failed_pks:
            raise forms.ValidationError(u"Could not recognize the following groups: {pks}.".format(pks=", ".join(failed_pks)))

        if self.max_entries != None and len(objs) > self.max_entries:
            raise forms.ValidationError(u"You can select at most %s entries only." % self.max_entries)

        return objs
