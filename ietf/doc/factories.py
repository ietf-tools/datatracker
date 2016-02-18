import factory

from ietf.doc.models import Document

class DocumentFactory(factory.DjangoModelFactory):
    class Meta:
        model = Document

    type_id = 'draft'
    title = factory.Faker('sentence',nb_words=6)
    rev = '00'
    group = None

    @factory.lazy_attribute_sequence
    def name(self, n):
        return '%s-%s-%s-%s%d'%( 
              self.type_id,
              'bogusperson',
              self.group.acronym if self.group else 'netherwhere',
              'musings',
              n,
            )
