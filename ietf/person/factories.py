# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import factory
from factory.fuzzy import FuzzyChoice
import faker 
import faker.config
import os
import random
from PIL import Image

from unidecode import unidecode
from unicodedata import normalize

from django.conf import settings
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils.encoding import force_str

import debug                            # pyflakes:ignore

from ietf.person.models import Person, Alias, Email, PersonalApiKey, PersonApiKeyEvent, PERSON_API_KEY_ENDPOINTS
from ietf.person.name import normalize_name, unidecode_name


fake = faker.Factory.create()

def setup():
    global acceptable_fakers
    # The transliteration of some Arabic and Devanagari names introduces
    # non-alphabetic characters that don't work with the draft author
    # extraction code, and also don't seem to match the way people with Arabic
    # names romanize Arabic names.  Exclude those locales from name generation
    # in order to avoid test failures.
    locales = set( [ l for l in faker.config.AVAILABLE_LOCALES if not (l.startswith('ar_') or l.startswith('sg_') or l=='fr_QC') ] )
    acceptable_fakers = [faker.Faker(locale) for locale in locales]
setup()

def random_faker():
    global acceptable_fakers
    return random.sample(acceptable_fakers, 1)[0]

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ('username',)
        exclude = ['faker', ]
        skip_postgeneration_save = True

    faker = factory.LazyFunction(random_faker)
    # normalize these i18n Unicode strings in the same way the database does
    first_name = factory.LazyAttribute(lambda o: normalize("NFKC", o.faker.first_name()))
    last_name = factory.LazyAttribute(lambda o: normalize("NFKC", o.faker.last_name()))
    email = factory.LazyAttributeSequence(lambda u, n: '%s.%s_%d@%s'%( slugify(unidecode(u.first_name)),
                                                slugify(unidecode(u.last_name)), n, fake.domain_name())) # type: ignore
    username = factory.LazyAttribute(lambda u: u.email)

    # Consider using PostGenerationMethodCall instead
    @factory.post_generation
    def set_password(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        obj.set_password( '%s+password' % obj.username ) # pylint: disable=no-value-for-parameter
        obj.save()

class PersonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Person
        skip_postgeneration_save = True

    user = factory.SubFactory(UserFactory)
    name = factory.LazyAttribute(lambda p: normalize_name('%s %s'%(p.user.first_name, p.user.last_name)))
    # Some i18n names, e.g., "शिला के.सी." have a dot at the end that is also part of the ASCII, e.g., "Shilaa Kesii."
    # That trailing dot breaks extract_authors(). Avoid this issue by stripping the dot from the ASCII.
    # Some others have a trailing semicolon (e.g., "உயிரோவியம் தங்கராஐ;") - strip those, too.
    ascii = factory.LazyAttribute(lambda p: force_str(unidecode_name(p.name)).rstrip(".;"))

    class Params:
        with_bio = factory.Trait(biography = "\n\n".join(fake.paragraphs())) # type: ignore

    @factory.post_generation
    def default_aliases(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        make_alias = getattr(AliasFactory, 'create' if create else 'build')
        make_alias(person=obj,name=obj.name)
        make_alias(person=obj,name=obj.ascii)
        if obj.name != obj.plain_name():
            make_alias(person=obj,name=obj.plain_name())
        if obj.ascii != obj.plain_ascii():
            make_alias(person=obj,name=obj.plain_ascii())

    @factory.post_generation
    def default_emails(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        if extracted is None:
            extracted = True
        if create and extracted:
            make_email = getattr(EmailFactory, 'create' if create else 'build')
            make_email(person=obj, address=obj.user.email)

    @factory.post_generation
    def default_photo(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        import atexit
        if obj.biography:
            photo_name = obj.photo_name()
            media_name = "%s/%s.jpg" % (settings.PHOTOS_DIRNAME, photo_name)
            obj.photo = media_name
            obj.photo_thumb = media_name
            photodst = os.path.join(settings.PHOTOS_DIR,  photo_name + '.jpg')
            img = Image.new('RGB', (200, 200))
            img.save(photodst)
            def delete_file(file):
                os.unlink(file)
            atexit.register(delete_file, photodst)
            obj.save()

class AliasFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Alias

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        person = kwargs['person']
        name = kwargs['name']
        existing_aliases = set(model_class.objects.filter(person=person).values_list('name', flat=True))
        if not name in existing_aliases:
            obj = model_class(*args, **kwargs)
            obj.save()
            return obj

    name = factory.Faker('name')

def fake_email_address(n):
    address_field = [ f for f in Email._meta.fields if f.name == 'address'][0]
    count = 0
    while True:
        address = '%s.%s_%d@%s' % (
            slugify(unidecode(fake.first_name())),
            slugify(unidecode(fake.last_name())),
            n, fake.domain_name()
        )
        count += 1
        if len(address) <= address_field.max_length:
            break
        if count >= 10:
            raise RuntimeError("Failed generating a fake email address to fit in Email.address(max_length=%s)"%address_field.max_lenth)
    return address

class EmailFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Email
        django_get_or_create = ('address',)

    address = factory.Sequence(fake_email_address)
    person = factory.SubFactory(PersonFactory)

    active = True
    primary = False
    origin = factory.LazyAttribute(lambda obj: obj.person.user.username if obj.person.user else '')


class PersonalApiKeyFactory(factory.django.DjangoModelFactory):
    person = factory.SubFactory(PersonFactory)
    endpoint = FuzzyChoice(v for v, n in PERSON_API_KEY_ENDPOINTS)
    
    class Meta:
        model = PersonalApiKey
        skip_postgeneration_save = True

    @factory.post_generation
    def validate_model(obj, create, extracted, **kwargs):
        """Validate the model after creation
        
        Passing validate_model=False will disable the validation.
        """
        do_clean =  True if extracted is None else extracted
        if do_clean:
            obj.full_clean()


class PersonApiKeyEventFactory(factory.django.DjangoModelFactory):
    key = factory.SubFactory(PersonalApiKeyFactory)
    person = factory.LazyAttribute(lambda o: o.key.person)
    type = 'apikey_login'
    desc = factory.Faker('sentence', nb_words=6)

    class Meta:
        model = PersonApiKeyEvent
