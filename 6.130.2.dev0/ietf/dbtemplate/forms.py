# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django import forms
from django.core.exceptions import ValidationError
from django.template import Context

from ietf.dbtemplate.models import DBTemplate
from ietf.dbtemplate.template import PlainTemplate, RSTTemplate, DjangoTemplate

import debug                            # pyflakes:ignore

class DBTemplateForm(forms.ModelForm):

    def clean_content(self):
        try:
            content = self.cleaned_data['content']
            if   self.instance.type.slug == 'rst':
                RSTTemplate(content).render(Context({}))
            elif self.instance.type.slug == 'django':
                DjangoTemplate(content).render(Context({}))
            elif self.instance.type.slug == 'plain':
                PlainTemplate(content).render(Context({}))
            else:
                raise ValidationError("Unexpected DBTemplate.type.slug: %s" % self.type.slug)
        except Exception as e:
            raise ValidationError(e)
        return content
                
    class Meta:
        model = DBTemplate
        fields = ('content', )
