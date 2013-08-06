from django import forms

from ietf.dbtemplate.models import DBTemplate


class DBTemplateForm(forms.ModelForm):

    class Meta:
        model = DBTemplate
        fields = ('content', )
