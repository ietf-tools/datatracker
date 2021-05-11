# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import debug    # pyflakes:ignore
import factory
import factory.fuzzy
import datetime

from typing import Optional         # pyflakes:ignore

from django.conf import settings

from ietf.doc.models import ( Document, DocEvent, NewRevisionDocEvent, DocAlias, State, DocumentAuthor,
    StateDocEvent, BallotPositionDocEvent, BallotDocEvent, BallotType, IRSGBallotDocEvent, TelechatDocEvent,
    DocumentActionHolder)
from ietf.group.models import Group

def draft_name_generator(type_id,group,n):
        return '%s-%s-%s-%s%d'%( 
              type_id,
              'bogusperson',
              group.acronym if group else 'netherwhere',
              'musings',
              n,
            )

class BaseDocumentFactory(factory.DjangoModelFactory):
    class Meta:
        model = Document

    title = factory.Faker('sentence',nb_words=5)
    abstract = factory.Faker('paragraph', nb_sentences=5)
    rev = '00'
    std_level_id = None                 # type: Optional[str]
    intended_std_level_id = None
    time = datetime.datetime.now()
    expires = factory.LazyAttribute(lambda o: o.time+datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE))
    pages = factory.fuzzy.FuzzyInteger(2,400)


    @factory.lazy_attribute_sequence
    def name(self, n):
        return draft_name_generator(self.type_id,self.group,n)

    newrevisiondocevent = factory.RelatedFactory('ietf.doc.factories.NewRevisionDocEventFactory','doc')

    @factory.post_generation
    def other_aliases(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        alias = DocAliasFactory(name=obj.name)
        alias.docs.add(obj)
        if create and extracted:
            for name in extracted:
                alias = DocAliasFactory(name=name)
                alias.docs.add(obj)

    @factory.post_generation
    def states(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        if create and extracted:
            for (state_type_id,state_slug) in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id,slug=state_slug))
            if obj.type_id == 'draft':
                if not obj.states.filter(type_id='draft-iesg').exists():
                    obj.set_state(State.objects.get(type_id='draft-iesg', slug='idexists'))

    @factory.post_generation
    def authors(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        if create and extracted:
            order = 0
            for person in extracted:
                DocumentAuthor.objects.create(document=obj, person=person, email=person.email(), order=order)
                order += 1

    @factory.post_generation
    def relations(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        if create and extracted:
            for (rel_id, doc) in extracted:
                if isinstance(doc, Document):
                    docalias = doc.docalias.first()
                elif isinstance(doc, DocAlias):
                    docalias = doc
                else:
                    continue
                obj.relateddocument_set.create(relationship_id=rel_id, target=docalias)

    @classmethod
    def _after_postgeneration(cls, obj, create, results=None):
        """Save again the instance if creating and at least one hook ran."""
        if create and results:
            # Some post-generation hooks ran, and may have modified us.
            obj._has_an_event_so_saving_is_allowed = True
            obj.save()

#TODO remove this - rename BaseDocumentFactory to DocumentFactory
class DocumentFactory(BaseDocumentFactory):

    type_id = 'draft'
    group = factory.SubFactory('ietf.group.factories.GroupFactory',acronym='none')


class IndividualDraftFactory(BaseDocumentFactory):

    type_id = 'draft'
    group = factory.SubFactory('ietf.group.factories.GroupFactory',acronym='none')

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for (state_type_id,state_slug) in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id,slug=state_slug))
            if not obj.get_state('draft-iesg'):
                obj.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))
        else:
            obj.set_state(State.objects.get(type_id='draft',slug='active'))
            obj.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))

class IndividualRfcFactory(IndividualDraftFactory):

    alias2 = factory.RelatedFactory('ietf.doc.factories.DocAliasFactory','document',name=factory.Sequence(lambda n: 'rfc%04d'%(n+1000)))

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for (state_type_id,state_slug) in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id,slug=state_slug))
        else:
            obj.set_state(State.objects.get(type_id='draft',slug='rfc'))

class WgDraftFactory(BaseDocumentFactory):

    type_id = 'draft'
    group = factory.SubFactory('ietf.group.factories.GroupFactory',type_id='wg')
    stream_id = 'ietf'

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for (state_type_id,state_slug) in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id,slug=state_slug))
            if not obj.get_state('draft-iesg'):
                obj.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))
        else:
            obj.set_state(State.objects.get(type_id='draft',slug='active'))
            obj.set_state(State.objects.get(type_id='draft-stream-ietf',slug='wg-doc'))
            obj.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))

class WgRfcFactory(WgDraftFactory):

    alias2 = factory.RelatedFactory('ietf.doc.factories.DocAliasFactory','document',name=factory.Sequence(lambda n: 'rfc%04d'%(n+1000)))

    std_level_id = 'ps'

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for (state_type_id,state_slug) in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id,slug=state_slug))
            if not obj.get_state('draft-iesg'):
                obj.set_state(State.objects.get(type_id='draft-iesg', slug='pub'))
        else:
            obj.set_state(State.objects.get(type_id='draft',slug='rfc'))
            obj.set_state(State.objects.get(type_id='draft-iesg', slug='pub'))


class RgDraftFactory(BaseDocumentFactory):

    type_id = 'draft'
    group = factory.SubFactory('ietf.group.factories.GroupFactory',type_id='rg')
    stream_id = 'irtf'

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for (state_type_id,state_slug) in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id,slug=state_slug))
            if not obj.get_state('draft-iesg'):
                obj.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))
        else:
            obj.set_state(State.objects.get(type_id='draft',slug='active'))
            obj.set_state(State.objects.get(type_id='draft-stream-irtf',slug='active'))
            obj.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))


class RgRfcFactory(RgDraftFactory):

    alias2 = factory.RelatedFactory('ietf.doc.factories.DocAliasFactory','document',name=factory.Sequence(lambda n: 'rfc%04d'%(n+1000)))

    std_level_id = 'inf'

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for (state_type_id,state_slug) in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id,slug=state_slug))
            if not obj.get_state('draft-stream-irtf'):
                obj.set_state(State.objects.get(type_id='draft-stream-irtf', slug='pub'))
            if not obj.get_state('draft-iesg'):
                obj.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))
        else:
            obj.set_state(State.objects.get(type_id='draft',slug='rfc'))
            obj.set_state(State.objects.get(type_id='draft-stream-irtf', slug='pub'))
            obj.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))


class CharterFactory(BaseDocumentFactory):

    type_id = 'charter'
    group = factory.SubFactory('ietf.group.factories.GroupFactory',type_id='wg')
    name = factory.LazyAttribute(lambda o: 'charter-ietf-%s'%o.group.acronym)

    @factory.post_generation
    def set_group_charter_document(obj, create, extracted, **kwargs):
        if not create:
            return
        obj.group.charter = extracted or obj
        obj.group.save()

class ConflictReviewFactory(BaseDocumentFactory):
    type_id='conflrev'
    
    @factory.post_generation
    def review_of(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            obj.relateddocument_set.create(relationship_id='conflrev',target=extracted.docalias.first())
        else:
            obj.relateddocument_set.create(relationship_id='conflrev',target=DocumentFactory(type_id='draft',group=Group.objects.get(type_id='individ')).docalias.first())

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for state in extracted:
                obj.set_state(state)
        else:
            obj.set_state(State.objects.get(type_id='conflrev',slug='iesgeval'))

# This is very skeletal. It is enough for the tests that use it now, but when it's needed, it will need to be improved with, at least, a group generator that backs the object with a review team.
class ReviewFactory(BaseDocumentFactory):
    type_id = 'review'
    name = factory.LazyAttribute(lambda o: 'review-doesnotexist-00-%s-%s'%(o.group.acronym,datetime.date.today().isoformat()))
    group = factory.SubFactory('ietf.group.factories.GroupFactory',type_id='review')

class DocAliasFactory(factory.DjangoModelFactory):
    class Meta:
        model = DocAlias

    @factory.post_generation
    def document(self, create, extracted, **kwargs):
        if create and extracted:
            self.docs.add(extracted)

    @factory.post_generation
    def docs(self, create, extracted, **kwargs):
        if create and extracted:
            for doc in extracted:
                if not doc in self.docs.all():
                    self.docs.add(doc)


class DocEventFactory(factory.DjangoModelFactory):
    class Meta:
        model = DocEvent

    type = 'added_comment'
    by = factory.SubFactory('ietf.person.factories.PersonFactory')
    doc = factory.SubFactory(DocumentFactory)
    desc = factory.Faker('sentence',nb_words=6)

    @factory.lazy_attribute
    def rev(self):
        return self.doc.rev

class TelechatDocEventFactory(DocEventFactory):
    class Meta:
        model = TelechatDocEvent

    telechat_date = datetime.datetime.today()+datetime.timedelta(days=14)
    type = 'scheduled_for_telechat'

class NewRevisionDocEventFactory(DocEventFactory):
    class Meta:
        model = NewRevisionDocEvent

    type = 'new_revision'
    rev = '00'

    @factory.lazy_attribute
    def desc(self):
         return 'New version available %s-%s'%(self.doc.name,self.rev)

class StateDocEventFactory(DocEventFactory):
    class Meta:
        model = StateDocEvent

    type = 'changed_state'
    state_type_id = 'draft-iesg'

    @factory.post_generation
    def state(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            (state_type_id, state_slug) = extracted
            obj.state = State.objects.get(type_id=state_type_id,slug=state_slug)
        else:
            obj.state = State.objects.get(type_id='draft-iesg',slug='ad-eval')
        obj.save()

# All of these Ballot* factories are extremely skeletal. Flesh them out as needed by tests.
class BallotTypeFactory(factory.DjangoModelFactory):
    class Meta:
        model = BallotType
        django_get_or_create = ('slug','doc_type_id')

    doc_type_id = 'draft'
    slug = 'approve'


class BallotDocEventFactory(DocEventFactory):
    class Meta:
        model = BallotDocEvent

    ballot_type = factory.SubFactory(BallotTypeFactory)
    type = 'created_ballot'

class IRSGBallotDocEventFactory(BallotDocEventFactory):
    class Meta:
        model = IRSGBallotDocEvent

    duedate = datetime.datetime.now() + datetime.timedelta(days=14)
    ballot_type = factory.SubFactory(BallotTypeFactory, slug='irsg-approve')

class BallotPositionDocEventFactory(DocEventFactory):
    class Meta:
        model = BallotPositionDocEvent

    type = 'changed_ballot_position'

    # This isn't right - it needs to build a ballot for the same doc as this position
    # For now, deal with this in test code by building BallotDocEvent and BallotPositionDocEvent
    # separately and passing the same doc into thier factories.
    ballot = factory.SubFactory(BallotDocEventFactory) 

    balloter = factory.SubFactory('ietf.person.factories.PersonFactory')
    pos_id = 'discuss'

class DocumentActionHolderFactory(factory.DjangoModelFactory):
    class Meta:
        model = DocumentActionHolder
        
    document = factory.SubFactory(WgDraftFactory)
    person = factory.SubFactory('ietf.person.factories.PersonFactory')

class DocumentAuthorFactory(factory.DjangoModelFactory):
    class Meta:
        model = DocumentAuthor

    document = factory.SubFactory(DocumentFactory)
    person = factory.SubFactory('ietf.person.factories.PersonFactory')
    email = factory.LazyAttribute(lambda obj: obj.person.email())
    affiliation = factory.Faker('company')
    country = factory.Faker('country')
    order = factory.LazyAttribute(lambda o: o.document.documentauthor_set.count() + 1)

class WgDocumentAuthorFactory(DocumentAuthorFactory):
    document = factory.SubFactory(WgDraftFactory)
