# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-

from datetime import datetime
from django.db import models
from django.db.models import ForeignKey
from django.template.defaultfilters import slugify

import debug                            # pyflakes:ignore

class Status(models.Model):
    name = 'Status'
    
    date = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(blank=True, null=True, unique=True, editable=False)
    title = models.CharField(max_length=255, verbose_name="Status title", help_text="Your site status notification title.")
    body = models.CharField(max_length=255, verbose_name="Status body", help_text="Your site status notification body.", unique=False)    
    active = models.BooleanField(default=True, verbose_name="Active?", help_text="Only active messages will be shown.")
    by = ForeignKey('person.Person', on_delete=models.CASCADE)
    page = models.TextField(blank=True, null=True, verbose_name="More detail (markdown)", help_text="More detail shown after people click 'Read more'. If empty no 'read more' will be shown")

    def __str__(self):
        return "{} {} {} {}".format(self.date, self.active, self.by, self.title)

    def save(self, *args, **kwargs):
        super(Status, self).save(*args, **kwargs)
        self.date = self.date or datetime.now()
        self.slug = slugify("%s-%s-%s-%s" % (self.date.year, self.date.month, self.date.day, self.title))

