from django.db import models

from ietf.group.models import Group


TEMPLATE_TYPES = (
    ('plain', 'Plain'),
    ('rst', 'reStructuredText'),
    ('django', 'Django'),
    )


class DBTemplate(models.Model):
    path = models.CharField(
        max_length=255,
        unique=True,
        blank=False,
        null=False,
        )
    title = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        )
    help_text = models.TextField(
        blank=True,
        null=True,
        )
    template_type = models.CharField(
        max_length=10,
        choices=TEMPLATE_TYPES,
        default='rst',
        )
    content = models.TextField(
        blank=False,
        null=False,
        )
    group = models.ForeignKey(
        Group,
        blank=True,
        null=True,
        )

    def __unicode__(self):
        return self.title
