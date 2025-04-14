# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import factory
import random

from faker import Faker

from ietf.nomcom.models import (
    NomCom,
    Position,
    Feedback,
    Nominee,
    NomineePosition,
    Nomination,
    Topic,
)
from ietf.group.factories import GroupFactory
from ietf.person.factories import PersonFactory

import debug  # pyflakes:ignore

cert = b"""-----BEGIN CERTIFICATE-----
MIIDHjCCAgagAwIBAgIJAKDCCjbQboJzMA0GCSqGSIb3DQEBCwUAMBMxETAPBgNV
BAMMCE5vbUNvbTE1MB4XDTE0MDQwNDIxMTQxNFoXDTE2MDQwMzIxMTQxNFowEzER
MA8GA1UEAwwITm9tQ29tMTUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIB
AQC2QXCsAitYSOgPYor77zQnEeHuVqlcuhpH1wpKB+N6WcScA5N3AnX9uZEFOt6M
cJ+MCiHECdqDlH6npQTJlpCpIVgAD4B6xzjRBRww8d3lClA/kKwsKzuX93RS0Uv3
0hAD6q9wjqK/m6vR5Y1SsvJYV0y+Yu5j9xUEsojMH7O3NlXWAYOb6oH+f/X7PX27
IhtiCwfICMmVWh/hKeXuFx6HSOcH3gZ6Tlk1llfDbE/ArpsZ6JmnLn73+64yqIoO
ZOc4JJUPrdsmbNwXoxQSQhrpwjN8NpSkQaJbHGB3G+OWvP4fpqcweFHxlEq1Hhef
uR9E6jc3qwxVQfwjbcq6N/4JAgMBAAGjdTBzMB0GA1UdDgQWBBTJow+TJynRWsTQ
LzoS861FGb/rxDAOBgNVHQ8BAf8EBAMCBLAwDwYDVR0TAQH/BAUwAwEB/zAcBgNV
HREEFTATgRFub21jb20xNUBpZXRmLm9yZzATBgNVHSUEDDAKBggrBgEFBQcDBDAN
BgkqhkiG9w0BAQsFAAOCAQEAJwLapB9u5N3iK6SCTqh+PVkigZeB2YMVBW8WA3Ut
iRPBj+jHWOpF5pzZHTOcNaAxDEG9lyIlcWqc93A24K/Gen11Tx0hO4FAPOG0+PP8
4lx7F6xeeyUNR44pInrB93G2q0jl+3wjZH8uhBKlGji4UTMpDPpEl6uiyQCbkMMm
Vr7HZH5Dv/lsjGHHf8uJO7+mcMh+tqxLn3DzPrm61OfeWdkoVX2pTz0imRQ3Es+8
I7zNMk+fNNaEEyPnEyHfuWq0uD/qKeP27NZIoINy6E3INQ5QaE2uc1nQULg5y7uJ
toX3j+FUe2UiUak3ACXdrOPSsFP0KRrFwuMnuHHXkGj/Uw==
-----END CERTIFICATE-----
"""

key = b"""-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC2QXCsAitYSOgP
Yor77zQnEeHuVqlcuhpH1wpKB+N6WcScA5N3AnX9uZEFOt6McJ+MCiHECdqDlH6n
pQTJlpCpIVgAD4B6xzjRBRww8d3lClA/kKwsKzuX93RS0Uv30hAD6q9wjqK/m6vR
5Y1SsvJYV0y+Yu5j9xUEsojMH7O3NlXWAYOb6oH+f/X7PX27IhtiCwfICMmVWh/h
KeXuFx6HSOcH3gZ6Tlk1llfDbE/ArpsZ6JmnLn73+64yqIoOZOc4JJUPrdsmbNwX
oxQSQhrpwjN8NpSkQaJbHGB3G+OWvP4fpqcweFHxlEq1HhefuR9E6jc3qwxVQfwj
bcq6N/4JAgMBAAECggEAb5SS4YwWc193S2v+QQ2KdVz6YEuINq/tRQw/TWGVACQT
PZzm3FaSXDsOsRAAjiSpWTgewgFyWVpBTGu4CZ73g8RZNvhGpWRwwW8KemCpg/8T
cEcnUYdKXdhuzAE9LETb7znwHM4Gj55DzCZopjfOLQ2Ne4XgAy2THaQcIjRKd6Bw
3mteJ2ityDj3iFN7cq9ntDzp+2BqLOi7AZmLntmUZxtkPCT6k5/dcKFYQW9Eb3bt
MON+BIYVzqhAijkP/cAWmbgZAP9EFng5PpE1lc/shl0W8eX4yvjNoMPRq3wphS4j
L16VncUeDep3vR0CECx7gnTfR0uCDEgKow50pzGQAQKBgQDaQWwK/o39zI3lCGzy
oSNJRNQJ/iZBkbbwpCCaka7VnBfd0ZH54VEWL3oMTkkWRSZtjsPAqT+ndwZitm0D
Kww9FUDMP7j/tMOwAUHYfjYFqFTn6ipkBuby9tbZtL7lgJO6Iu2Qk3afqADD0kcP
zRLxcYSLjrmp9NyUlNnpswR4CQKBgQDVxjwG/orCmiuyA1Bu4u1hdUD0w9CKnyjp
VTbkv8lxk5V3pYzms2Awb0X43W2OioYGBk5yw+9GCF//xCrfbGV7BLZnDTGShjkJ
8oTpLPGBsDSfaKVXE3Hko4LVLBMQIm0tDyuPD1Naia7ZknYn906skonEG8WgHUyp
c/BgkvzWAQKBgBdojuL6/FWtO8bFyZGYUMWJ+Uf9FzNPIpTatZh+aYcFj9W9pW9s
iBreCrQJLXOTBRUZC8u9G1Olw2yQ7k45rr1aazG83+WlCJv29o32s2qV7E1XYyaJ
SvniGZcN+K96w91h46Lu/fkPts1J309FinOU3kdtjmI5HfNdp6WWCrOpAoGBAMjc
TEaeIK8cwPWwG4E1A6pQy8mvu2Ckj4I+KSfh9FsdOpGDIdMas8SOqQZet7P5AFjk
0A0RgN8iu2DMZyQq62cdVG2bffqY1zs7fhrBueILOEaXwtMAWEFmSWYW1YqRbleq
K1luIvms6HdSIGcI/gk0XvG+zn/VR9ToNPHo6lwBAoGBAIrYGYPf+cjZ1V/tNqnL
IecEZb4Gkp1hVhOpNT4U+T2LROxrZtFxxsw2vuIRa5a5FtMbDq9Xyhkm0QppliBd
KQ38jTT0EaD2+vstTqL8vxupo25RQWV1XsmLL4pLbKnm2HnnwB3vEtsiokWKW0q0
Tdb0MiLc+r/zvx8oXtgDjDUa
-----END PRIVATE KEY-----
"""


def provide_private_key_to_test_client(testcase):
    session = testcase.client.session
    session["NOMCOM_PRIVATE_KEY_%s" % testcase.nc.year()] = key.decode("utf8")
    session.save()


def nomcom_kwargs_for_year(year=None, *args, **kwargs):
    if not year:
        year = random.randint(1990, 2100)
    if "group__state_id" not in kwargs:
        kwargs["group__state_id"] = "active"
    if "group__acronym" not in kwargs:
        kwargs["group__acronym"] = "nomcom%d" % year
    if "group__name" not in kwargs:
        kwargs["group__name"] = "TEST VERSION of NomCom %d/%d" % (year, year + 1)
    return kwargs


class NomComFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NomCom
        skip_postgeneration_save = True

    group = factory.SubFactory(GroupFactory, type_id="nomcom")

    public_key = factory.django.FileField(data=cert)

    @factory.post_generation
    def populate_positions(
        obj, create, extracted, **kwargs
    ):  # pylint: disable=no-self-argument
        """
        Create a set of nominees and positions unless NomcomFactory is called
        with populate_positions=False
        """
        if extracted is None:
            extracted = True
        if create and extracted:
            nominees = [NomineeFactory(nomcom=obj) for i in range(4)]
            positions = [PositionFactory(nomcom=obj) for i in range(3)]

            def npc(position, nominee, state_id):
                return NomineePosition.objects.create(
                    position=position, nominee=nominee, state_id=state_id
                )

            # This gives us positions with 0, 1 and 2 nominees, and
            # one person who's been nominated for more than one position
            npc(positions[0], nominees[0], "accepted")
            npc(positions[1], nominees[0], "accepted")
            npc(positions[1], nominees[1], "accepted")
            npc(positions[0], nominees[2], "pending")
            npc(positions[0], nominees[3], "declined")

    @factory.post_generation
    def populate_personnel(
        obj, create, extracted, **kwargs
    ):  # pylint: disable=no-self-argument
        """
        Create a default set of role holders, unless the factory is called
        with populate_personnel=False
        """
        if extracted is None:
            extracted = True
        if create and extracted:
            # roles= ['chair', 'advisor'] + ['member']*10
            roles = ["chair", "advisor", "member"]
            for role in roles:
                p = PersonFactory()
                obj.group.role_set.create(
                    name_id=role, person=p, email=p.email_set.first()
                )

    @factory.post_generation
    def populate_topics(
        obj, create, extracted, **kwargs
    ):  # pylint: disable=no-self-argument
        """
        Create a set of topics unless the factory is called with populate_topics=False
        """
        if extracted is None:
            extracted = True
        if create and extracted:
            for i in range(3):
                TopicFactory(nomcom=obj)


class PositionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Position

    name = factory.Faker("sentence", nb_words=5)
    is_open = True
    accepting_nominations = True
    accepting_feedback = True


class NomineeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Nominee

    nomcom = factory.SubFactory(NomComFactory)
    person = factory.SubFactory(PersonFactory)
    email = factory.LazyAttribute(lambda obj: obj.person.email())


class NomineePositionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NomineePosition

    position = factory.SubFactory(PositionFactory)
    nominee = factory.SubFactory(NomineeFactory)
    state_id = "accepted"


class FeedbackFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Feedback
        skip_postgeneration_save = True

    nomcom = factory.SubFactory(NomComFactory)
    subject = factory.Faker("sentence")
    type_id = "comment"

    @factory.post_generation
    def comments(obj, create, extracted, **kwargs):
        comment_text = Faker().paragraph()
        obj.comments = obj.nomcom.encrypt(comment_text)
        obj.save()


class TopicFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Topic

    nomcom = factory.SubFactory(NomComFactory)
    subject = factory.Faker("sentence")
    accepting_feedback = True
    audience_id = "general"


class NominationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Nomination

    nominee = factory.SubFactory(NomineeFactory)
    position = factory.SubFactory(NomineePositionFactory)
    candidate_name = factory.LazyAttribute(lambda obj: obj.nominee.person.name)
    candidate_email = factory.LazyAttribute(lambda obj: obj.nominee.person.email())
    candidate_phone = factory.Faker("phone_number")
    comments = factory.SubFactory(FeedbackFactory)
    nominator_email = factory.LazyAttribute(lambda obj: obj.person.user.email)
    person = factory.SubFactory(PersonFactory)
    share_nominator = False
