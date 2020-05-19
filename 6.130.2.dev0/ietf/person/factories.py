# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import factory
import faker 
import faker.config
import os
import random
import shutil

from unidecode import unidecode

from django.conf import settings
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils.encoding import force_text

import debug                            # pyflakes:ignore

from ietf.person.models import Person, Alias, Email
from ietf.person.name import normalize_name, unidecode_name


fake = faker.Factory.create()

def random_faker():
    # The transliteration of some arabic and devanagari names introduces
    # non-alphabetic characgters that don't work with the draft author
    # extraction code, and also don't seem to match the way people with arabic
    # names romanize arabic names.  Exlude those locales from name generation
    # in order to avoid test failures.
    locales = set( [ l for l in faker.config.AVAILABLE_LOCALES if not (l.startswith('ar_') or l.startswith('sg_')) ] )
    return faker.Faker(random.sample(locales, 1)[0])

class UserFactory(factory.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ('username',)
        exclude = ['faker', ]

    faker = factory.LazyFunction(random_faker)
    first_name = factory.LazyAttribute(lambda o: o.faker.first_name())
    last_name = factory.LazyAttribute(lambda o: o.faker.last_name())
    email = factory.LazyAttributeSequence(lambda u, n: '%s.%s_%d@%s'%( slugify(unidecode(u.first_name)),
                                                slugify(unidecode(u.last_name)), n, fake.domain_name()))
    username = factory.LazyAttribute(lambda u: u.email)

    @factory.post_generation
    def set_password(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        obj.set_password( '%s+password' % obj.username ) # pylint: disable=no-value-for-parameter

class PersonFactory(factory.DjangoModelFactory):
    class Meta:
        model = Person

    user = factory.SubFactory(UserFactory)
    name = factory.LazyAttribute(lambda p: normalize_name('%s %s'%(p.user.first_name, p.user.last_name)))
    ascii = factory.LazyAttribute(lambda p: force_text(unidecode_name(p.name)))

    class Params:
        with_bio = factory.Trait(biography = "\n\n".join(fake.paragraphs()))

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
            photosrc = os.path.join(settings.TEST_DATA_DIR, "profile-default.jpg")
            photodst = os.path.join(settings.PHOTOS_DIR,  photo_name + '.jpg')
            if not os.path.exists(photodst):
                shutil.copy(photosrc, photodst)
            def delete_file(file):
                os.unlink(file)
            atexit.register(delete_file, photodst)

class AliasFactory(factory.DjangoModelFactory):
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

class EmailFactory(factory.DjangoModelFactory):
    class Meta:
        model = Email
        django_get_or_create = ('address',)

    address = factory.Sequence(fake_email_address)
    person = factory.SubFactory(PersonFactory)

    active = True
    primary = False
    origin = factory.LazyAttribute(lambda obj: obj.person.user.username if obj.person.user else '')
