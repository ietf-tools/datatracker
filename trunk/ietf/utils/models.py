# Copyright The IETF Trust 2015, All Rights Reserved

from django.db import models

class DumpInfo(models.Model):
    date = models.DateTimeField()
    host = models.CharField(max_length=128)
    tz   = models.CharField(max_length=32, default='UTC')
    
class VersionInfo(models.Model):
    time    = models.DateTimeField(auto_now=True)
    command = models.CharField(max_length=32)
    switch  = models.CharField(max_length=16)
    version = models.CharField(max_length=64)
    used    = models.BooleanField(default=True)
    class Meta:
        verbose_name_plural = 'VersionInfo'
        
