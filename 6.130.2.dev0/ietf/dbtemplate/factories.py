import factory

from ietf.dbtemplate.models import DBTemplate

class DBTemplateFactory(factory.DjangoModelFactory):
    class Meta:
        model = DBTemplate

