# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-

# Taken from/inspired by
# https://stackoverflow.com/questions/55147169/django-admin-jsonfield-default-empty-dict-wont-save-in-admin
# 
# JSONField should recognize {}, (), and [] as valid, non-empty JSON
# values.  However, the base Field class excludes them
import jsonfield

from ietf.utils.fields import IETFJSONField as FormIETFJSONField


class IETFJSONField(jsonfield.JSONField):
    form_class = FormIETFJSONField

    def __init__(self, *args, empty_values=FormIETFJSONField.empty_values, accepted_empty_values=None, **kwargs):
        if accepted_empty_values is None:
            accepted_empty_values = []
        self.empty_values = [x
                             for x in empty_values
                             if x not in accepted_empty_values]
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        if issubclass(kwargs['form_class'], FormIETFJSONField):
            kwargs.setdefault('empty_values', self.empty_values)
        return super().formfield(**{**kwargs})
