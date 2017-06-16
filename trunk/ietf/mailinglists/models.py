# Copyright The IETF Trust 2016, All Rights Reserved

from django.db import models
from django.core.validators import validate_email

from ietf.person.models import Person

class List(models.Model):
    name = models.CharField(max_length=32)
    description = models.CharField(max_length=256)
    advertised = models.BooleanField(default=True)
    def __unicode__(self):
        return "<List: %s>" % self.name

class Subscribed(models.Model):
    time = models.DateTimeField(auto_now_add=True)
    email = models.CharField(max_length=64, validators=[validate_email])
    lists = models.ManyToManyField(List)
    def __unicode__(self):
        return "<Subscribed: %s at %s>" % (self.email, self.time)
    class Meta:
        verbose_name_plural = "Subscribed"

class Whitelisted(models.Model):
    time = models.DateTimeField(auto_now_add=True)
    email = models.CharField("Email address", max_length=64, validators=[validate_email])
    by = models.ForeignKey(Person)
    def __unicode__(self):
        return "<Whitelisted: %s at %s>" % (self.email, self.time)
    class Meta:
        verbose_name_plural = "Whitelisted"

