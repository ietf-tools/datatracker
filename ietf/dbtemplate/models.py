# -*- coding: utf-8 -*-
# Copyright The IETF Trust 2012-2020, All Rights Reserved


from django.db import models
from django.core.exceptions import ValidationError
from django.template import Context

from ietf.group.models import Group
from ietf.name.models import DBTemplateTypeName
from ietf.utils.models import ForeignKey


TEMPLATE_TYPES = (
    ('plain', 'Plain'),
    ('rst', 'reStructuredText'),
    ('django', 'Django'),
    )


class DBTemplate(models.Model):
    path = models.CharField( max_length=255, unique=True, blank=False, null=False, )
    title = models.CharField( max_length=255, blank=False, null=False, )
    variables = models.TextField( blank=True, null=True, )
    type = ForeignKey( DBTemplateTypeName, )
    content = models.TextField( blank=False, null=False, )
    group = ForeignKey( Group, blank=True, null=True, )

    def __str__(self):
        return self.title

    def clean(self):
        from ietf.dbtemplate.template import PlainTemplate, RSTTemplate, DjangoTemplate
        try:
            if   self.type.slug == 'rst':
                RSTTemplate(self.content).render(Context({}))
            elif self.type.slug == 'django':
                DjangoTemplate(self.content).render(Context({}))
            elif self.type.slug == 'plain':
                PlainTemplate(self.content).render(Context({}))
            else:
                raise ValidationError("Unexpected DBTemplate.type.slug: %s" % self.type.slug)
        except Exception as e:
            raise ValidationError(e)

