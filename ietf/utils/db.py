# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-

# Taken from/inspired by
# https://stackoverflow.com/questions/55147169/django-admin-jsonfield-default-empty-dict-wont-save-in-admin
# 
# JSONField should recognize {}, (), and [] as valid, non-empty JSON
# values.  However, the base Field class excludes them

import jsonfield
from django.db import models

from ietf.utils.fields import IETFJSONField as FormIETFJSONField, EmptyAwareJSONField as FormEmptyAwareJSONField


class EmptyAwareJSONField(models.JSONField):
    form_class = FormEmptyAwareJSONField

    def __init__(self, *args, empty_values=FormEmptyAwareJSONField.empty_values, accepted_empty_values=None, **kwargs):
        if accepted_empty_values is None:
            accepted_empty_values = []
        self.empty_values = [x
                             for x in empty_values
                             if x not in accepted_empty_values]
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        if 'form_class' not in kwargs or issubclass(kwargs['form_class'], FormEmptyAwareJSONField):
            kwargs.setdefault('empty_values', self.empty_values)
        return super().formfield(**{**kwargs})


class IETFJSONField(jsonfield.JSONField):  # pragma: no cover
    # Deprecated - use EmptyAwareJSONField instead (different base class requires a
    # new field name)
    # Remove this class when migrations are squashed and it is no longer referenced
    form_class = FormIETFJSONField

    def __init__(self, *args, empty_values=FormIETFJSONField.empty_values, accepted_empty_values=None, **kwargs):
        if accepted_empty_values is None:
            accepted_empty_values = []
        self.empty_values = [x
                             for x in empty_values
                             if x not in accepted_empty_values]
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        if 'form_class' not in kwargs or issubclass(kwargs['form_class'], FormIETFJSONField):
            kwargs.setdefault('empty_values', self.empty_values)
        return super().formfield(**{**kwargs})
