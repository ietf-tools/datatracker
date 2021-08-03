import factory

from ietf.dbtemplate.models import DBTemplate

class DBTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DBTemplate

