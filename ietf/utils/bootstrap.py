# Copyright The IETF Trust 2016-2020, All Rights Reserved


import django_bootstrap5.renderers

class SeparateErrorsFromHelpTextFieldRenderer(django_bootstrap5.renderers.FieldRenderer):
    def append_to_field(self, html):
        if self.field_help:
            html += f'<div class="form-text">{self.field_help}</div>'
        for e in self.field_errors:
            html += f'<div class="alert alert-danger my-3">{e}</div>'
        return html