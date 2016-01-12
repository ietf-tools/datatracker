import json

from django.utils.html import escape
from django import forms
from django.core.urlresolvers import reverse as urlreverse

from ietf.ipr.models import IprDisclosureBase

def select2_id_ipr_title_json(value):
    return json.dumps([{ "id": o.pk, "text": escape(u"%s <%s>" % (o.title, o.time.date().isoformat())) } for o in value])

class SearchableIprDisclosuresField(forms.CharField):
    """Server-based multi-select field for choosing documents using
    select2.js.

    The field uses a comma-separated list of primary keys in a
    CharField element as its API with some extra attributes used by
    the Javascript part."""

    def __init__(self,
                 max_entries=None, # max number of selected objs
                 model=IprDisclosureBase,
                 hint_text="Type in terms to search disclosure title",
                 *args, **kwargs):
        kwargs["max_length"] = 1000
        self.max_entries = max_entries
        self.model = model

        super(SearchableIprDisclosuresField, self).__init__(*args, **kwargs)

        self.widget.attrs["class"] = "select2-field form-control"
        self.widget.attrs["data-placeholder"] = hint_text
        if self.max_entries != None:
            self.widget.attrs["data-max-entries"] = self.max_entries

    def parse_select2_value(self, value):
        return [x.strip() for x in value.split(",") if x.strip()]

    def prepare_value(self, value):
        if not value:
            value = ""
        if isinstance(value, basestring):
            pks = self.parse_select2_value(value)
            # if the user posted a non integer value we need to remove it
            for key in pks:
                if not key.isdigit():
                    pks.remove(key)
            value = self.model.objects.filter(pk__in=pks)
        if isinstance(value, self.model):
            value = [value]

        self.widget.attrs["data-pre"] = select2_id_ipr_title_json(value)

        # doing this in the constructor is difficult because the URL
        # patterns may not have been fully constructed there yet
        self.widget.attrs["data-ajax-url"] = urlreverse("ipr_ajax_search")

        return u",".join(unicode(e.pk) for e in value)

    def clean(self, value):
        value = super(SearchableIprDisclosuresField, self).clean(value)
        pks = self.parse_select2_value(value)

        if not all([ key.isdigit() for key in pks ]):
            raise forms.ValidationError(u'You must enter IPR ID(s) as integers')

        objs = self.model.objects.filter(pk__in=pks)

        found_pks = [str(o.pk) for o in objs]
        failed_pks = [x for x in pks if x not in found_pks]
        if failed_pks:
            raise forms.ValidationError(u"Could not recognize the following {model_name}s: {pks}. You can only input {model_name}s already registered in the Datatracker.".format(pks=", ".join(failed_pks), model_name=self.model.__name__.lower()))

        if self.max_entries != None and len(objs) > self.max_entries:
            raise forms.ValidationError(u"You can select at most %s entries only." % self.max_entries)

        return objs
