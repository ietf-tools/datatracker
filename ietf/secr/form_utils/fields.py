from django import forms

from form_utils.widgets import ClearableFileInput

class FakeEmptyFieldFile(object):
    """
    A fake FieldFile that will convice a FileField model field to
    actually replace an existing file name with an empty string.
    
    FileField.save_form_data only overwrites its instance data if the
    incoming form data evaluates to True in a boolean context (because
    an empty file input is assumed to mean "no change"). We want to be
    able to clear it without requiring the use of a model FileField
    subclass (keeping things at the form level only). In order to do
    this we need our form field to return a value that evaluates to
    True in a boolean context, but to the empty string when coerced to
    unicode. This object fulfills that requirement.

    It also needs the _committed attribute to satisfy the test in
    FileField.pre_save.

    This is, of course, hacky and fragile, and depends on internal
    knowledge of the FileField and FieldFile classes. But it will
    serve until Django FileFields acquire a native ability to be
    cleared (ticket 7048).

    """
    def __unicode__(self):
        return u''
    _committed = True

class ClearableFileField(forms.MultiValueField):
    default_file_field_class = forms.FileField
    widget = ClearableFileInput
    
    def __init__(self, file_field=None, template=None, *args, **kwargs):
        file_field = file_field or self.default_file_field_class(*args,
                                                                  **kwargs)
        fields = (file_field, forms.BooleanField(required=False))
        kwargs['required'] = file_field.required
        kwargs['widget'] = self.widget(file_widget=file_field.widget,
                                       template=template)
        super(ClearableFileField, self).__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        if data_list[1] and not data_list[0]:
            return FakeEmptyFieldFile()
        return data_list[0]

class ClearableImageField(ClearableFileField):
    default_file_field_class = forms.ImageField
