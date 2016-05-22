import bootstrap3.renderers

class SeparateErrorsFromHelpTextFieldRenderer(bootstrap3.renderers.FieldRenderer):
    def append_to_field(self, html):
        if self.field_help:
            html += u'<div class="help-block">{}</div>'.format(self.field_help)
        for e in self.field_errors:
            html += u'<div class="alert alert-danger">{}</div>'.format(e)
        return html
