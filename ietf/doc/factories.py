# Copyright The IETF Trust 2016-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import debug    # pyflakes:ignore
import factory
import factory.fuzzy
import datetime

from typing import Any  # pyflakes:ignore

from django.conf import settings
from django.utils import timezone

from ietf.doc.models import ( Document, DocEvent, NewRevisionDocEvent, State, DocumentAuthor,
    StateDocEvent, BallotPositionDocEvent, BallotDocEvent, BallotType, IRSGBallotDocEvent, TelechatDocEvent,
    DocumentActionHolder, BofreqEditorDocEvent, BofreqResponsibleDocEvent, DocExtResource )
from ietf.group.models import Group
from ietf.person.factories import PersonFactory
from ietf.group.factories import RoleFactory
from ietf.name.models import ExtResourceName
from ietf.utils.text import xslugify
from ietf.utils.timezone import date_today


def draft_name_generator(type_id,group,n):
        return '%s-%s-%s-%s%d'%( 
              type_id,
              'bogusperson',
              group.acronym if group else 'netherwhere',
              'musings',
              n,
            )

class BaseDocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document
        skip_postgeneration_save = True

    # n.b., a few attributes are typed as Any so mypy won't complain when we override in subclasses
    title = factory.Faker('sentence',nb_words=5)
    abstract: Any = factory.Faker('paragraph', nb_sentences=5)
    rev = '00'
    std_level_id: Any = None
    intended_std_level_id = None
    time = timezone.now()
    expires: Any = factory.LazyAttribute(
        lambda o: o.time+datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE)
    )
    pages = factory.fuzzy.FuzzyInteger(2,400)


    @factory.lazy_attribute_sequence
    def name(self, n):
        return draft_name_generator(self.type_id,self.group,n)

    @factory.post_generation
    def newrevisiondocevent(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        if create:
            if obj.type_id != "rfc":
                NewRevisionDocEventFactory(doc=obj)

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
                obj.relateddocument_set.create(relationship_id=rel_id, target=doc)

    @factory.post_generation
    def create_revisions(obj, create, extracted, **kwargs):  # pylint: disable=no-self-argument
        """Create additional revisions of the document

        Argument should be an iterable of revisions. Remember that range() is exclusive on the end
        index, so range(1, 10) stops at 9.
        """
        if create and extracted:
            for rev in extracted:
                e = NewRevisionDocEventFactory(doc=obj, rev=f'{rev:02d}')
                obj.rev = f'{rev:02d}'
                obj.save_with_history([e])

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


class RfcFactory(BaseDocumentFactory):
    type_id = "rfc"
    rev = ""
    rfc_number = factory.Sequence(lambda n: n + 1000)
    name = factory.LazyAttribute(lambda o: f"rfc{o.rfc_number:d}")
    expires = None

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for (state_type_id,state_slug) in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id,slug=state_slug))
        else:
            obj.set_state(State.objects.get(type_id='rfc',slug='published'))


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

class IndividualRfcFactory(RfcFactory):
    group = factory.SubFactory('ietf.group.factories.GroupFactory',acronym='none')


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


class WgRfcFactory(RfcFactory):
    group = factory.SubFactory('ietf.group.factories.GroupFactory',type_id='wg')
    stream_id = 'ietf'
    std_level_id = 'ps'


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


class RgRfcFactory(RfcFactory):
    group = factory.SubFactory('ietf.group.factories.GroupFactory',type_id='rg')
    stream_id = 'irtf'
    std_level_id = 'inf'


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

class StatusChangeFactory(BaseDocumentFactory):
    type_id='statchg'

    group = factory.SubFactory('ietf.group.factories.GroupFactory',acronym='iesg',type_id='ietf')
    name = factory.Sequence(lambda n: f'status-change-{n}-factoried')

    @factory.post_generation
    def changes_status_of(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for (rel, target) in extracted:
                obj.relateddocument_set.create(relationship_id=rel,target=target)
        else:
            obj.relateddocument_set.create(relationship_id='tobcp', target=WgRfcFactory())

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for state in extracted:
                obj.set_state(state)
        else:
            obj.set_state(State.objects.get(type_id='statchg',slug='appr-sent'))


class ConflictReviewFactory(BaseDocumentFactory):
    type_id='conflrev'

    group = factory.SubFactory('ietf.group.factories.GroupFactory',acronym='none')

    @factory.lazy_attribute_sequence
    def name(self, n):
        return draft_name_generator(self.type_id,self.group,n).replace('conflrev-','conflict-review-')
    
    @factory.post_generation
    def review_of(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            obj.relateddocument_set.create(relationship_id='conflrev',target=extracted)
        else:
            obj.relateddocument_set.create(relationship_id='conflrev',target=DocumentFactory(name=obj.name.replace('conflict-review-','draft-'),type_id='draft',group=Group.objects.get(type_id='individ')))


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
    name = factory.LazyAttribute(lambda o: 'review-doesnotexist-00-%s-%s'%(o.group.acronym,date_today().isoformat()))
    group = factory.SubFactory('ietf.group.factories.GroupFactory',type_id='review')

class DocEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocEvent

    type = 'added_comment'
    by = factory.SubFactory('ietf.person.factories.PersonFactory')
    doc: Any = factory.SubFactory(DocumentFactory)  # `Any` to appease mypy when a subclass overrides doc
    desc = factory.Faker('sentence',nb_words=6)

    @factory.lazy_attribute
    def rev(self):
        return self.doc.rev

class TelechatDocEventFactory(DocEventFactory):
    class Meta:
        model = TelechatDocEvent

    # note: this is evaluated at import time and not updated - all events will have the same telechat_date
    telechat_date = timezone.now()+datetime.timedelta(days=14)
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
        skip_postgeneration_save = True

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
class BallotTypeFactory(factory.django.DjangoModelFactory):
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

    duedate = timezone.now() + datetime.timedelta(days=14)
    ballot_type = factory.SubFactory(BallotTypeFactory, slug='irsg-approve')

class BallotPositionDocEventFactory(DocEventFactory):
    class Meta:
        model = BallotPositionDocEvent

    type = 'changed_ballot_position'
    ballot = factory.SubFactory(BallotDocEventFactory)
    doc = factory.SelfAttribute('ballot.doc')  # point to same doc as the ballot
    balloter = factory.SubFactory('ietf.person.factories.PersonFactory')
    pos_id = 'discuss'

class DocumentActionHolderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocumentActionHolder
        
    document = factory.SubFactory(WgDraftFactory)
    person = factory.SubFactory('ietf.person.factories.PersonFactory')

class DocumentAuthorFactory(factory.django.DjangoModelFactory):
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

class BofreqEditorDocEventFactory(DocEventFactory):
    class Meta:
        model = BofreqEditorDocEvent
        skip_postgeneration_save = True

    type = "changed_editors"
    doc = factory.SubFactory('ietf.doc.factories.BofreqFactory')


    @factory.post_generation
    def editors(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            obj.editors.set(extracted)
        else:
            obj.editors.set(PersonFactory.create_batch(3))
        obj.desc = f'Changed editors to {", ".join(obj.editors.values_list("name",flat=True)) or "(None)"}'
        obj.save()

class BofreqResponsibleDocEventFactory(DocEventFactory):
    class Meta:
        model = BofreqResponsibleDocEvent
        skip_postgeneration_save = True

    type = "changed_responsible"
    doc = factory.SubFactory('ietf.doc.factories.BofreqFactory')


    @factory.post_generation
    def responsible(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            obj.responsible.set(extracted)
        else:
            ad = RoleFactory(group__type_id='area',name_id='ad').person
            obj.responsible.set([ad])
        obj.desc = f'Changed responsible leadership to {", ".join(obj.responsible.values_list("name",flat=True)) or "(None)"}'
        obj.save()        

class BofreqFactory(BaseDocumentFactory):
    type_id = 'bofreq'
    title = factory.Faker('sentence')
    name = factory.LazyAttribute(lambda o: 'bofreq-%s-%s'%(xslugify(o.requester_lastname), xslugify(o.title)))

    bofreqeditordocevent = factory.RelatedFactory('ietf.doc.factories.BofreqEditorDocEventFactory','doc')
    bofreqresponsibledocevent = factory.RelatedFactory('ietf.doc.factories.BofreqResponsibleDocEventFactory','doc')

    class Params:
        requester_lastname = factory.Faker('last_name')

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for (state_type_id,state_slug) in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id,slug=state_slug))
        else:
            obj.set_state(State.objects.get(type_id='bofreq',slug='proposed'))


class ProceedingsMaterialDocFactory(BaseDocumentFactory):
    type_id = 'procmaterials'
    abstract = ''
    expires = None

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for (state_type_id,state_slug) in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id,slug=state_slug))
        else:
            obj.set_state(State.objects.get(type_id='procmaterials', slug='active'))

class DocExtResourceFactory(factory.django.DjangoModelFactory):

    name = factory.Iterator(ExtResourceName.objects.filter(type_id='url'))
    value = factory.Faker('url')
    doc = factory.SubFactory('ietf.doc.factories.BaseDocumentFactory')
    class Meta:
        model = DocExtResource

class EditorialDraftFactory(BaseDocumentFactory):

    type_id = 'draft'
    group = factory.SubFactory('ietf.group.factories.GroupFactory',acronym='rswg', type_id='edwg')
    stream_id = 'editorial'

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
            obj.set_state(State.objects.get(type_id='draft-stream-editorial',slug='active'))
            obj.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))

class EditorialRfcFactory(RgRfcFactory):
    pass
    
class StatementFactory(BaseDocumentFactory):
    type_id = "statement"
    title = factory.Faker("sentence")
    group = factory.SubFactory("ietf.group.factories.GroupFactory", acronym="iab")

    name = factory.LazyAttribute(
        lambda o: "statement-%s-%s" % (xslugify(o.group.acronym), xslugify(o.title))
    )
    uploaded_filename = factory.LazyAttribute(lambda o: f"{o.name}-{o.rev}.md")

    published_statement_event = factory.RelatedFactory(
        "ietf.doc.factories.DocEventFactory",
        "doc",
        type="published_statement",
        time=timezone.now() - datetime.timedelta(days=1),
    )

    @factory.post_generation
    def states(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for state_type_id, state_slug in extracted:
                obj.set_state(State.objects.get(type_id=state_type_id, slug=state_slug))
        else:
            obj.set_state(State.objects.get(type_id="statement", slug="active"))

class SubseriesFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document
        skip_postgeneration_save = True

    @factory.lazy_attribute_sequence
    def name(self, n):
        return f"{self.type_id}{n}"
    
    @factory.post_generation
    def contains(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for doc in extracted:
                obj.relateddocument_set.create(relationship_id="contains",target=doc)
        else:
            obj.relateddocument_set.create(relationship_id="contains", target=RfcFactory())

class BcpFactory(SubseriesFactory):
    type_id="bcp"

class StdFactory(SubseriesFactory):
    type_id="std"

class FyiFactory(SubseriesFactory):
    type_id="fyi"
