from django.db import models

from ietf.group.models import Group
from ietf.name.models import GroupTypeName


class NomComGroup(Group):
    public_key = models.TextField(verbose_name="Public Key", blank=True)

    class Meta:
        verbose_name_plural = "NomCom groups"
        verbose_name = "NomCom group"

    def save(self, *args, **kwargs):
        if not self.id:
            try:
                self.type = GroupTypeName.objects.get(slug='nomcom')
            except GroupTypeName.DoesNotExist:
                pass

        super(NomComGroup, self).save(*args, **kwargs)
