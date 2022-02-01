# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import django_bootstrap5.renderers

class SeparateErrorsFromHelpTextFieldRenderer(django_bootstrap5.renderers.FieldRenderer):
    def append_to_field(self, html):
        if self.field_help:
            html += '<div class="form-text">{}</div>'.format(self.field_help)
        for e in self.field_errors:
            html += '<div class="alert alert-danger my-3">{}</div>'.format(e)
        return html