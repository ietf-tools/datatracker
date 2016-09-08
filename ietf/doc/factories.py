import factory

from ietf.doc.models import Document, DocEvent, NewRevisionDocEvent, DocAlias, State, DocumentAuthor

def draft_name_generator(type_id,group,n):
        return '%s-%s-%s-%s%d'%( 
              type_id,
              'bogusperson',
              group.acronym if group else 'netherwhere',
              'musings',
              n,
            )

class DocumentFactory(factory.DjangoModelFactory):
    class Meta:
        model = Document

    type_id = 'draft'
    title = factory.Faker('sentence',nb_words=6)
    rev = '00'
    group = factory.SubFactory('ietf.group.factories.GroupFactory',type_id='individ')
    std_level_id = None
    intended_std_level_id = None

    @factory.lazy_attribute_sequence
    def name(self, n):
        return draft_name_generator(self.type_id,self.group,n)

    newrevisiondocevent = factory.RelatedFactory('ietf.doc.factories.NewRevisionDocEventFactory','doc')

    alias = factory.RelatedFactory('ietf.doc.factories.DocAliasFactory','document')

    @factory.post_generation
    def other_aliases(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        if create and extracted:
            for alias in extracted:
                obj.docalias_set.create(name=alias) 

    @factory.post_generation
    def states(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        if create and extracted:
            for (state_type_id,state_slug) in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id,slug=state_slug))

    @factory.post_generation
    def authors(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        if create and extracted:
            order = 0
            for email in extracted:
                DocumentAuthor.objects.create(document=obj, author=email, order=order)
                order += 1

    @classmethod
    def _after_postgeneration(cls, obj, create, results=None):
        """Save again the instance if creating and at least one hook ran."""
        if create and results:
            # Some post-generation hooks ran, and may have modified us.
            obj._has_an_event_so_saving_is_allowed = True
            obj.save()


class DocAliasFactory(factory.DjangoModelFactory):
    class Meta:
        model = DocAlias

    document = factory.SubFactory('ietf.doc.factories.DocumentFactory')

    @factory.lazy_attribute
    def name(self):
        return self.document.name
    

class DocEventFactory(factory.DjangoModelFactory):
    class Meta:
        model = DocEvent

    type = 'added_comment'
    by = factory.SubFactory('ietf.person.factories.PersonFactory')
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

