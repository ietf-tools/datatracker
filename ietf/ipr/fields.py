# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import json

from django.utils.html import escape
from django import forms
from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.ipr.models import IprDisclosureBase
from ietf.utils.fields import SearchableField


def select2_id_ipr_title(objs):
    return [{
        "id": o.pk,
        "text": escape("%s <%s>" % (o.title, o.time.date().isoformat())),
    } for o in objs]

def select2_id_ipr_title_json(value):
    return json.dumps(select2_id_ipr_title(value))

class SearchableIprDisclosuresField(SearchableField):
    """Server-based multi-select field for choosing documents using select2.js"""
    model = IprDisclosureBase
    default_hint_text = "Type in terms to search disclosure title"

    def validate_pks(self, pks):
        for pk in pks:
            if not pk.isdigit():
                raise forms.ValidationError("You must enter IPR ID(s) as integers (Unexpected value: %s)" % pk)

    def get_model_instances(self, item_ids):
        for key in item_ids:
            if not key.isdigit():
                item_ids.remove(key)
        return super(SearchableIprDisclosuresField, self).get_model_instances(item_ids)

    def make_select2_data(self, model_instances):
        return select2_id_ipr_title(model_instances)

    def ajax_url(self):
        return urlreverse('ietf.ipr.views.ajax_search')
