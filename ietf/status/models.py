# Copyright The IETF Trust 2024, All Rights Reserved
# -*- coding: utf-8 -*-

from django.utils import timezone
from django.db import models
from django.db.models import ForeignKey

import debug                            # pyflakes:ignore

class Status(models.Model):
    name = 'Status'
    
    date = models.DateTimeField(default=timezone.now)
    slug = models.SlugField(blank=False, null=False, unique=True)
    title = models.CharField(max_length=255, verbose_name="Status title", help_text="Your site status notification title.")
    body = models.CharField(max_length=255, verbose_name="Status body", help_text="Your site status notification body.", unique=False)    
    active = models.BooleanField(default=True, verbose_name="Active?", help_text="Only active messages will be shown.")
    by = ForeignKey('person.Person', on_delete=models.CASCADE)
    page = models.TextField(blank=True, null=True, verbose_name="More detail (markdown)", help_text="More detail shown after people click 'Read more'. If empty no 'read more' will be shown")

    def __str__(self):
        return "{} {} {} {}".format(self.date, self.active, self.by, self.title)
    class Meta:
        verbose_name_plural = "statuses"
