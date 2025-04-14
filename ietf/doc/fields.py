# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import json

from typing import Type  # pyflakes:ignore

from django.utils.html import escape
from django.db import models  # pyflakes:ignore
from django.db.models import Q
from django.urls import reverse as urlreverse

import debug  # pyflakes:ignore

from ietf.doc.models import Document
from ietf.doc.utils import uppercase_std_abbreviated_name
from ietf.utils.fields import SearchableField


def select2_id_doc_name(model, objs):
    return (
        [
            {
                "id": o.pk,
                "url": (
                    o.get_absolute_url()
                    if model == Document
                    else o.document.get_absolute_url()
                ),
                "text": escape(uppercase_std_abbreviated_name(o.name)),
            }
            for o in objs
        ]
        if objs
        else []
    )


def select2_id_doc_name_json(model, objs):
    return json.dumps(select2_id_doc_name(model, objs))


class SearchableDocumentsField(SearchableField):
    """Server-based multi-select field for choosing documents using select2.js."""

    model = Document  # type: Type[models.Model]
    default_hint_text = "Type name to search for document"

    def __init__(self, doc_type="draft", *args, **kwargs):
        super(SearchableDocumentsField, self).__init__(*args, **kwargs)
        self.doc_type = doc_type

    def doc_type_filter(self, queryset):
        """Filter to include only desired doc type"""
        return queryset.filter(type=self.doc_type)

    def get_model_instances(self, item_ids):
        """Get model instances corresponding to item identifiers in select2 field value

        Accepts both names and pks as IDs
        """
        names = [i for i in item_ids if not i.isdigit()]
        ids = [i for i in item_ids if i.isdigit()]
        objs = self.model.objects.filter(Q(name__in=names) | Q(id__in=ids))
        return self.doc_type_filter(objs)

    def make_select2_data(self, model_instances):
        """Get select2 data items"""
        return select2_id_doc_name(self.model, model_instances)

    def ajax_url(self):
        """Get the URL for AJAX searches"""
        return urlreverse(
            "ietf.doc.views_search.ajax_select2_search_docs",
            kwargs={
                "doc_type": self.doc_type,
                "model_name": self.model.__name__.lower(),
            },
        )


class SearchableDocumentField(SearchableDocumentsField):
    """Specialized to only return one Document"""

    max_entries = 1
