# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.conf import settings
from django.core.validators import validate_email
from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from ietf.person.models import Person
from ietf.utils.models import ForeignKey

@python_2_unicode_compatible
class List(models.Model):
    name = models.CharField(max_length=32)
    description = models.CharField(max_length=256)
    advertised = models.BooleanField(default=True)

    def __str__(self):
        return "<List: %s>" % self.name
    def info_url(self):
        return settings.MAILING_LIST_INFO_URL % {'list_addr': self.name }

@python_2_unicode_compatible
class Subscribed(models.Model):
    time = models.DateTimeField(auto_now_add=True)
    email = models.CharField(max_length=128, validators=[validate_email])
    lists = models.ManyToManyField(List)
    def __str__(self):
        return "<Subscribed: %s at %s>" % (self.email, self.time)
    class Meta:
        verbose_name_plural = "Subscribed"

@python_2_unicode_compatible
class Whitelisted(models.Model):
    time = models.DateTimeField(auto_now_add=True)
    email = models.CharField("Email address", max_length=64, validators=[validate_email])
    by = ForeignKey(Person)
    def __str__(self):
        return "<Whitelisted: %s at %s>" % (self.email, self.time)
    class Meta:
        verbose_name_plural = "Whitelisted"

