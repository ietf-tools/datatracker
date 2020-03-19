# Copyright The IETF Trust 2015-2020, All Rights Reserved

import itertools

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

class ForeignKey(models.ForeignKey):
    "A local ForeignKey proxy which provides the on_delete value required under Django 2.0."
    def __init__(self, to, on_delete=models.CASCADE, **kwargs):
        return super(ForeignKey, self).__init__(to, on_delete=on_delete, **kwargs)
        
class OneToOneField(models.OneToOneField):
    "A local OneToOneField proxy which provides the on_delete value required under Django 2.0."
    def __init__(self, to, on_delete=models.CASCADE, **kwargs):
        return super(OneToOneField, self).__init__(to, on_delete=on_delete, **kwargs)
        
def object_to_dict(instance):
    """
    Similar to django.forms.models.model_to_dict() but more comprehensive.

    Taken from https://stackoverflow.com/questions/21925671/#answer-29088221
    with a minor tweak: .id --> .pk
    """
    opts = instance._meta
    data = {}
    for f in itertools.chain(opts.concrete_fields, opts.private_fields):
        data[f.name] = f.value_from_object(instance)
    for f in opts.many_to_many:
        data[f.name] = [i.pk for i in f.value_from_object(instance)]
    return data        
