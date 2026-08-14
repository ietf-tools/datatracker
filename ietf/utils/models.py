# Copyright The IETF Trust 2015-2026, All Rights Reserved

import itertools

from django.db import models


class DirtyBits(models.Model):
    """A weak semaphore mechanism for coordination with celery beat tasks

    Web workers will set the "dirty_time" value for a given dirtybit slug.
    Celery workers will do work if "processed_time" < "dirty_time" and update
    "processed_time".
    """

    class Slugs(models.TextChoices):
        RFCINDEX = "rfcindex", "RFC Index"
        ERRATA = "errata", "Errata Tags"

    # next line can become `...choices=Slugs)` when we get to Django 5.x
    slug = models.CharField(max_length=40, blank=False, choices=Slugs.choices, unique=True)
    dirty_time = models.DateTimeField(null=True, blank=True)
    processed_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "dirty bits"

    
class DumpInfo(models.Model):
    date = models.DateTimeField()
    host = models.CharField(max_length=128)
    tz   = models.CharField(max_length=32, default='UTC')

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
