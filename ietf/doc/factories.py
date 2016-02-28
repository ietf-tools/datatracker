import factory

from ietf.doc.models import Document, DocEvent, NewRevisionDocEvent
from ietf.person.factories import PersonFactory

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

    newrevisiondocevent = factory.RelatedFactory('ietf.doc.factories.NewRevisionDocEventFactory','doc')

class DocEventFactory(factory.DjangoModelFactory):
    class Meta:
        model = DocEvent

    type = 'added_comment'
    by = factory.SubFactory(PersonFactory)
    doc = factory.SubFactory(DocumentFactory)
    desc = factory.Faker('sentence',nb_words=6)

class NewRevisionDocEventFactory(DocEventFactory):
    class Meta:
        model = NewRevisionDocEvent

    type = 'new_revision'
    rev = '00'

    @factory.lazy_attribute
    def desc(self):
         return 'New version available %s-%s'%(self.doc.name,self.rev)
