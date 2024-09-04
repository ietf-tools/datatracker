# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.conf import settings
from django.core.validators import validate_email
from django.db import models

from ietf.person.models import Person
from ietf.utils.models import ForeignKey


# NonWgMailingList is a temporary bridging class to hold information known about mailman2
# while decoupling from mailman2 until we integrate with mailman3
class NonWgMailingList(models.Model):
    name = models.CharField(max_length=32)
    domain = models.CharField(max_length=32, default="ietf.org")
    description = models.CharField(max_length=256)

    def __str__(self):
        return "<NonWgMailingList: %s>" % self.name
    def info_url(self):
        return settings.MAILING_LIST_INFO_URL % {'list_addr': self.name.lower(), 'domain': self.domain.lower() }

# Allowlisted is unused, but is not being dropped until its human-curated content 
# is archived outside this database.
class Allowlisted(models.Model):
    time = models.DateTimeField(auto_now_add=True)
    email = models.CharField("Email address", max_length=64, validators=[validate_email])
    by = ForeignKey(Person)
    def __str__(self):
        return "<Allowlisted: %s at %s>" % (self.email, self.time)
    class Meta:
        verbose_name_plural = "Allowlisted"

