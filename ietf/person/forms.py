# Copyright The IETF Trust 2018-2025, All Rights Reserved
# -*- coding: utf-8 -*-


from django import forms
from ietf.person.models import Person


class MergeForm(forms.Form):
    source = forms.IntegerField(label='Source Person ID')
    target = forms.IntegerField(label='Target Person ID')

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
    to = forms.CharField()
    frm = forms.CharField()
    reply_to = forms.CharField()
    subject = forms.CharField()
    body = forms.CharField(widget=forms.Textarea)

    def clean_to(self):
        addresses = self.cleaned_data['to']
        return addresses.split(',')

    def clean_reply_to(self):
        addresses = self.cleaned_data['reply_to']
        return addresses.split(',')
