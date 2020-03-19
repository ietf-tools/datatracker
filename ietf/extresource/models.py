# Copyright The IETF Trust 2020, All Rights Reserved
from django.db import models

from ietf.name.models import ExtResourceName, ExtResourceTypeName

# Create your models here.
class ExtResource(models.Model):
    name = models.ForeignKey(ExtResourceName, on_delete=models.CASCADE)
    value = models.CharField(max_length=2083) # 2083 is the maximum legal URL length