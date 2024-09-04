# Copyright The IETF Trust 2024, All Rights Reserved
import factory

from ietf.person.models import Person 
from .models import Message, SendQueue


class MessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Message

    by = factory.LazyFunction(lambda: Person.objects.get(name="(System)"))
    subject = factory.Faker("sentence")
    to = factory.Faker("email")
    frm = factory.Faker("email")
    cc = factory.Faker("email")
    bcc = factory.Faker("email")
    body = factory.Faker("paragraph")
    content_type = "text/plain"


class SendQueueFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SendQueue

    by = factory.LazyFunction(lambda: Person.objects.get(name="(System)"))
    message = factory.SubFactory(MessageFactory)
