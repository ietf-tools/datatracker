# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import models

import debug                            # pyflakes:ignore

from ietf.person.models import Person

class Status(models.Model):
    """ Status messages """

    date = models.DateField()
    active = models.BooleanField(default=True, help_text="Only active messages will be shown")
    by = ForeignKey(Person)
    message = models.CharField(max_length=255, help_text="Your status message.", unique=False)
    url = models.URLField()

    def __str__(self):
        return "{} {} {} {} {}".format(self.date, self.active, self.by, self.message, self.url)

