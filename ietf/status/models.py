# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import models
from django.db.models import ForeignKey
from django.template.defaultfilters import slugify

import debug                            # pyflakes:ignore

from ietf.person.models import Person

class Status(models.Model):
    name = 'Status'
    

    date = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(blank=True, null=True, unique=True, editable=False)
    title = models.CharField(max_length=255)
    body = models.CharField(max_length=255, help_text="Your status message.", unique=False)    
    active = models.BooleanField(default=True, help_text="Only active messages will be shown")
    by = ForeignKey('person.Person', on_delete=models.CASCADE)
    page = models.TextField(blank=True, null=True) # markdown page

    def __str__(self):
        return "{} {} {} {} {}".format(self.date, self.active, self.by, self.message, self.url)

    def save(self):
        self.slug = slugify(self.title)
        super(Program,self).save()
