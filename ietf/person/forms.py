# Copyright The IETF Trust 2018-2025, All Rights Reserved
# -*- coding: utf-8 -*-


from django import forms

from ietf.person.models import Person
from ietf.utils.fields import MultiEmailField, NameAddrEmailField


class MergeForm(forms.Form):
    source = forms.IntegerField(label='Source Person ID')
    target = forms.IntegerField(label='Target Person ID')

    def __init__(self, *args, **kwargs):
        self.readonly = False
        if 'readonly' in kwargs:
            self.readonly = kwargs.pop('readonly')
        super().__init__(*args, **kwargs)
        if self.readonly:
            self.fields['source'].widget.attrs['readonly'] = True
            self.fields['target'].widget.attrs['readonly'] = True

    def clean_source(self):
        return self.get_person(self.cleaned_data['source'])

    def clean_target(self):
        return self.get_person(self.cleaned_data['target'])

    def get_person(self, pk):
        try:
            return Person.objects.get(pk=pk)
        except Person.DoesNotExist:
            raise forms.ValidationError("ID does not exist")


class MergeRequestForm(forms.Form):
    to = MultiEmailField()
    frm = NameAddrEmailField()
    reply_to = MultiEmailField()
    subject = forms.CharField()
    body = forms.CharField(widget=forms.Textarea)
