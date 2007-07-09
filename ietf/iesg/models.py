# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models

class TelechatMinutes(models.Model):
    telechat_date = models.DateField(null=True, blank=True)
    telechat_minute = models.TextField(blank=True)
    exported = models.IntegerField(null=True, blank=True)
    def get_absolute_url(self):
	return "/iesg/telechat/%d/" % self.id
    class Meta:
        db_table = 'telechat_minutes'

