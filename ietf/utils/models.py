# Copyright The IETF Trust 2015, All Rights Reserved

from django.db import models

class DumpInfo(models.Model):
    date = models.DateTimeField()
    host = models.CharField(max_length=128)
    tz   = models.CharField(max_length=32, default='UTC')
    
