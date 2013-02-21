from django.contrib import admin
from django import forms

from form_utils.fields import ClearableFileField

class ClearableFileFieldsAdmin(admin.ModelAdmin):
    def formfield_for_dbfield(self, db_field, **kwargs):
        field = super(ClearableFileFieldsAdmin, self).formfield_for_dbfield(
            db_field, **kwargs)
        if isinstance(field, forms.FileField):
            field = ClearableFileField(field)
        return field
