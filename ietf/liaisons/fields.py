# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import json

from django.utils.html import escape
from django import forms
from django.urls import reverse as urlreverse

from ietf.liaisons.models import LiaisonStatement
from ietf.utils.fields import SearchableField


def select2_id_liaison(objs):
    return [{
        "id": o.pk,
        "text":"[{}] {}".format(o.pk, escape(o.title)),
    } for o in objs]

def select2_id_liaison_json(objs):
    return json.dumps(select2_id_liaison(objs))

def select2_id_group_json(objs):
    return json.dumps([{ "id": o.pk, "text": escape(o.acronym) } for o in objs])


class SearchableLiaisonStatementsField(SearchableField):
    """Server-based multi-select field for choosing liaison statements using
    select2.js."""
    model = LiaisonStatement
    default_hint_text = "Type in title to search for document"

    def validate_pks(self, pks):
        for pk in pks:
            if not pk.isdigit():
                raise forms.ValidationError("Unexpected value: %s" % pk)

    def make_select2_data(self, model_instances):
        return select2_id_liaison(model_instances)

    def ajax_url(self):
        return urlreverse("ietf.liaisons.views.ajax_select2_search_liaison_statements")

    def describe_failed_pks(self, failed_pks):
        return "Could not recognize the following groups: {pks}.".format(pks=", ".join(failed_pks))
