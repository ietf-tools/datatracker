# Copyright The IETF Trust 2014-2025, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import json
import uuid
from unittest import mock

from io import StringIO, BytesIO
from PIL import Image
from pyquery import PyQuery

import django.core.signing
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.utils import IntegrityError
from django.http import HttpRequest
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse as urlreverse
from django.utils import timezone
from django.utils.encoding import iri_to_uri

import yaml

import debug                            # pyflakes:ignore

from ietf.community.models import CommunityList
from ietf.group.factories import RoleFactory
from ietf.group.models import Group
from ietf.message.models import Message
from ietf.nomcom.models import NomCom
from ietf.nomcom.test_data import nomcom_test_data
from ietf.nomcom.factories import NomComFactory, NomineeFactory, NominationFactory, FeedbackFactory, PositionFactory
from ietf.nomcom.utils import make_nomineeposition_for_newperson
from ietf.person.factories import (
    EmailFactory,
    PersonFactory,
    PersonApiKeyEventFactory,
    PersonUUIDFactory,
)
from ietf.person.models import Person, Alias, PersonApiKeyEvent, PersonUUID
from ietf.person.tasks import (purge_personal_api_key_events_task, push_person_uuids_task,
    check_person_uuids_task)
from ietf.person.utils import (merge_persons, determine_merge_order, send_merge_notification,
    handle_users, get_extra_primary, dedupe_aliases, move_related_objects, merge_nominees,
    handle_reviewer_settings, get_dots, assign_primary_uuid, ensure_primary_uuid,
    get_person_uuid_object)
from ietf.submit.utils import ensure_person_email_info_exists
from kombu.exceptions import OperationalError as KombuOperationalError
from ietf.review.models import ReviewerSettings
from ietf.utils.test_utils import TestCase, login_testing_unauthorized
from ietf.utils.mail import outbox, empty_outbox


def get_person_no_user():
    person = PersonFactory()
    person.user = None
    person.save()
    return person


class PersonTests(TestCase):
    def test_ajax_search_emails(self):
        person = PersonFactory()

        r = self.client.get(urlreverse("ietf.person.views.ajax_select2_search", kwargs={ "model_name": "email"}), dict(q=person.name))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data[0]["id"], person.email_address())

    def test_ajax_person_email_json(self):
        person = PersonFactory()
        EmailFactory.create_batch(5, person=person)
        primary_email = person.email()
        primary_email.primary = True
        primary_email.save()
        
        bad_url = urlreverse('ietf.person.ajax.person_email_json', kwargs=dict(personid=12345))
        url = urlreverse('ietf.person.ajax.person_email_json', kwargs=dict(personid=person.pk))
        
        login_testing_unauthorized(self, 'secretary', bad_url)
        r = self.client.get(bad_url)
        self.assertEqual(r.status_code, 404)
        self.client.logout()

        login_testing_unauthorized(self, 'secretary', url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertCountEqual(
            json.loads(r.content),
            [dict(address=email.address, primary=email.primary) for email in person.email_set.all()],
        )

    def test_default_email(self):
        person = PersonFactory()
        primary = person.email_set.get()
        self.assertEqual(primary.primary, True)
        self.assertEqual(primary.active, True)
        EmailFactory(person=person, primary=False, active=True)
        EmailFactory(person=person, primary=False, active=False)
        self.assertTrue(primary.address in person.formatted_email())

    def test_person_profile(self):
        person = PersonFactory(with_bio=True,pronouns_freetext="foo/bar")
        
        self.assertTrue(person.photo is not None)
        self.assertTrue(person.photo.name is not None)

        url = urlreverse("ietf.person.views.profile", kwargs={ "email_or_name": person.plain_name()})
        r = self.client.get(url)
        #debug.show('person.name')
        #debug.show('person.plain_name()')
        #debug.show('person.photo_name()')
        self.assertContains(r, person.photo_name(), status_code=200)
        self.assertContains(r, "foo/bar")
        q = PyQuery(r.content)
        self.assertIn("Photo of %s"%person.name, q("div.bio-text img").attr("alt"))

        bio_text  = q("div.bio-text").text()
        self.assertIsNotNone(bio_text)

        photo_url = q("div.bio-text img").attr("src")
        r = self.client.get(photo_url)
        self.assertEqual(r.status_code, 200)

    def test_person_profile_without_email(self):
        person = PersonFactory(name="foobar@example.com")
        # delete Email record
        person.email().delete()
        url = urlreverse("ietf.person.views.profile", kwargs={ "email_or_name": person.plain_name()})
        r = self.client.get(url)
        self.assertContains(r, person.name, status_code=200)

    def test_person_profile_by_uuid(self):
        person_a = PersonFactory(name="A Fine Person")
        uuid_a = person_a.uuids.first()
        url_a = urlreverse("ietf.person.views.profile_by_uuid", kwargs={"uuid": uuid_a.uuid})

        person_b = PersonFactory(name="Brilliant Person")
        uuid_b = person_b.uuids.first()
        url_b = urlreverse("ietf.person.views.profile_by_uuid", kwargs={"uuid": uuid_b.uuid})

        r = self.client.get(url_a)
        self.assertContains(r, person_a.name)
        self.assertNotContains(r, person_b.name)

        r = self.client.get(url_b)
        self.assertNotContains(r, person_a.name)
        self.assertContains(r, person_b.name)

        # Move b's UUID to a as a prior UUID, as a merge would...
        uuid_b.person = person_a
        uuid_b.primary = False
        uuid_b.save()
        # ... and the old address redirects to a's canonical one
        r = self.client.get(url_b)
        self.assertRedirects(r, url_a)
        r = self.client.get(url_b, follow=True)
        self.assertContains(r, person_a.name)
        self.assertNotContains(r, person_b.name)

    def test_person_profile_by_uuid_upper_case(self):
        person = PersonFactory()
        uuid_value = person.primary_uuid
        url = urlreverse(
            "ietf.person.views.profile_by_uuid", kwargs={"uuid": uuid_value}
        )
        upper = url.replace(str(uuid_value), str(uuid_value).upper())
        self.assertNotEqual(url, upper)
        r = self.client.get(upper)
        self.assertContains(r, person.name, status_code=200)

    def test_person_profile_by_uuid_unknown(self):
        url = urlreverse(
            "ietf.person.views.profile_by_uuid", kwargs={"uuid": uuid.uuid4()}
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_case_insensitive(self):
        # Case insensitive seach
        person = PersonFactory(name="Test Person")
        url = urlreverse("ietf.person.views.profile", kwargs={ "email_or_name": "test person"})
        r = self.client.get(url)
        self.assertContains(r, person.name, status_code=200)
        self.assertNotIn('More than one person', r.content.decode())

    def test_person_profile_duplicates(self):
        # same Person name and email - should not show on the profile as multiple Person records
        person = PersonFactory(name="bazquux@example.com", user__email="bazquux@example.com")
        url = urlreverse("ietf.person.views.profile", kwargs={ "email_or_name": person.plain_name()})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('More than one person', r.content.decode())

        # Change that person's name but leave their email address. Create a new person whose name
        # is the email address. This *should* be flagged as multiple Person records on the profile.
        person.name = 'different name'
        person.save()
        PersonFactory(name="bazquux@example.com")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn('More than one person', r.content.decode())

    def test_person_profile_404(self):
        urls = [
                urlreverse("ietf.person.views.profile", kwargs={ "email_or_name": "nonexistent@example.com"}),
                urlreverse("ietf.person.views.profile", kwargs={ "email_or_name": "Nonexistent Person"}),]

        for url in urls:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 404)

    def test_person_photo(self):
        person = PersonFactory(with_bio=True)
        
        self.assertTrue(person.photo is not None)
        self.assertTrue(person.photo.name is not None)

        url = urlreverse("ietf.person.views.photo", kwargs={ "email_or_name": person.email()})
        r = self.client.get(url)
        self.assertEqual(r['Content-Type'], 'image/jpg')
        self.assertEqual(r.status_code, 200)
        img = Image.open(BytesIO(r.content))
        self.assertEqual(img.width, 80)

        r = self.client.get(url+'?size=200')
        self.assertEqual(r['Content-Type'], 'image/jpg')
        self.assertEqual(r.status_code, 200)
        img = Image.open(BytesIO(r.content))
        self.assertEqual(img.width, 200)

    def test_person_photo_duplicates(self):
        person = PersonFactory(name="bazquux@example.com", user__username="bazquux@example.com", with_bio=True)
        PersonFactory(name="bazquux@example.com", user__username="foobar@example.com", with_bio=True)

        url = urlreverse("ietf.person.views.photo", kwargs={ "email_or_name": person.plain_name()})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_name_methods(self):
        person = PersonFactory(name="Dr. Jens F. Möller", )

        self.assertEqual(person.name, "Dr. Jens F. Möller" )
        self.assertEqual(person.ascii_name(), "Dr. Jens F. Moller" )
        self.assertEqual(person.plain_name(), "Jens Möller" )
        self.assertEqual(person.plain_ascii(), "Jens Moller" )
        self.assertEqual(person.initials(), "J. F.")
        self.assertEqual(person.first_name(), "Jens" )
        self.assertEqual(person.last_name(), "Möller" )

        person = PersonFactory(name="吴建平")
        # The following are probably incorrect because the given name should
        # be Jianping and the surname should be Wu ...
        # TODO: Figure out better handling for names with CJK characters.
        # Maybe use ietf.person.cjk.*
        self.assertEqual(person.ascii_name(), "Wu Jian Ping")

    def test_duplicate_person_name(self):
        empty_outbox()
        p = PersonFactory(name="Föö Bär")
        PersonFactory(name=p.name)
        self.assertTrue("possible duplicate" in str(outbox[0]["Subject"]).lower())

    def test_merge(self):
        url = urlreverse("ietf.person.views.merge")
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_merge_with_params(self):
        p1 = get_person_no_user()
        p2 = PersonFactory()
        url = urlreverse("ietf.person.views.merge_submit") + "?source={}&target={}".format(p1.pk, p2.pk)
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertContains(r, 'retaining login', status_code=200)

    def test_merge_with_params_bad_id(self):
        url = urlreverse("ietf.person.views.merge_submit") + "?source=1000&target=2000"
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertContains(r, 'ID does not exist', status_code=200)

    def test_merge_post(self):
        p1 = get_person_no_user()
        p2 = PersonFactory()
        url = urlreverse("ietf.person.views.merge_submit")
        expected_url = urlreverse("ietf.secr.rolodex.views.view", kwargs={'id': p2.pk})
        login_testing_unauthorized(self, "secretary", url)
        data = {'source': p1.pk, 'target': p2.pk}
        r = self.client.post(url, data, follow=True)
        self.assertRedirects(r, expected_url)
        self.assertContains(r, 'Merged', status_code=200)
        self.assertFalse(Person.objects.filter(pk=p1.pk))

    def test_absolute_url(self):
        p = PersonFactory()
        self.assertEqual(p.get_absolute_url(), iri_to_uri('/person/%s' % p.name))

    @override_settings(SERVE_CDN_PHOTOS=True)
    def test_cdn_photo_url_cdn_on(self):
        p = PersonFactory(with_bio=True)
        self.assertIn('cdn-cgi/image',p.cdn_photo_url())

    @override_settings(SERVE_CDN_PHOTOS=False)
    def test_cdn_photo_url_cdn_off(self):
        p = PersonFactory(with_bio=True)
        self.assertNotIn('cdn-cgi/photo',p.cdn_photo_url())

    def test_invalid_name_characters_rejected(self):
        for disallowed in "/:@":
            # build() does not save the new object
            person_with_bad_name = PersonFactory.build(name=f"I have a {disallowed}", user=None)
            with self.assertRaises(ValidationError, msg=f"Name with a {disallowed} char should be rejected"):
                person_with_bad_name.full_clean()  # calls validators (save() does *not*)


class PersonUtilsTests(TestCase):
    def test_determine_merge_order(self):
        p1 = get_person_no_user()
        p2 = PersonFactory()
        p3 = get_person_no_user()
        p4 = PersonFactory()

        # target has User
        results = determine_merge_order(p1, p2)
        self.assertEqual(results,(p1,p2))

        # source has User
        results = determine_merge_order(p2, p1)
        self.assertEqual(results,(p1,p2))
        
        # neither have User
        results = determine_merge_order(p1, p3)
        self.assertEqual(results,(p1,p3))

        # both have User
        today = timezone.now()
        p2.user.last_login = today
        p2.user.save()
        p4.user.last_login = today - datetime.timedelta(days=30)
        p4.user.save()
        results = determine_merge_order(p2, p4)
        self.assertEqual(results,(p4,p2))

    def test_send_merge_notification(self):
        person = PersonFactory()
        len_before = len(outbox)
        send_merge_notification(person,['Record Merged'])
        self.assertEqual(len(outbox),len_before+1)
        self.assertTrue('IETF Datatracker records merged' in outbox[-1]['Subject'])

    def test_handle_reviewer_settings(self):
        groups = Group.objects.all()
        # no ReviewerSettings
        source = PersonFactory()
        target = PersonFactory()
        result = handle_reviewer_settings(source, target)
        self.assertEqual(result, [])

        # source ReviewerSettings only
        source = PersonFactory()
        target = PersonFactory()
        ReviewerSettings.objects.create(team=groups[0],person=source,min_interval=14)
        result = handle_reviewer_settings(source, target)
        self.assertEqual(result, [])

        # source and target ReviewerSettings, non-conflicting
        source = PersonFactory()
        target = PersonFactory()
        rs1 = ReviewerSettings.objects.create(team=groups[0],person=source,min_interval=14)
        ReviewerSettings.objects.create(team=groups[1],person=target,min_interval=14)
        result = handle_reviewer_settings(source, target)
        self.assertEqual(result, [])

        # source and target ReviewerSettings, conflicting
        source = PersonFactory()
        target = PersonFactory()
        rs1 = ReviewerSettings.objects.create(team=groups[0],person=source,min_interval=14)
        ReviewerSettings.objects.create(team=groups[0],person=target,min_interval=7)
        self.assertEqual(source.reviewersettings_set.count(), 1)
        result = handle_reviewer_settings(source, target)
        self.assertEqual(result, ['REVIEWER SETTINGS ACTION: dropping duplicate ReviewSettings for team: {}'.format(rs1.team)])
        self.assertEqual(source.reviewersettings_set.count(), 0)
        self.assertEqual(target.reviewersettings_set.count(), 1)

    def test_handle_users(self):
        source1 = get_person_no_user()
        target1 = get_person_no_user()
        source2 = get_person_no_user()
        target2 = PersonFactory()
        source3 = PersonFactory()
        target3 = get_person_no_user()
        source4 = PersonFactory()
        target4 = PersonFactory()

        # no Users
        result = handle_users(source1, target1)
        self.assertTrue("DATATRACKER LOGIN ACTION: none" in result)

        # target user
        result = handle_users(source2, target2)
        self.assertTrue("DATATRACKER LOGIN ACTION: retaining login {}".format(target2.user) in result)

        # source user
        user = source3.user
        result = handle_users(source3, target3)
        self.assertTrue("DATATRACKER LOGIN ACTION: retaining login {}".format(user) in result)
        self.assertTrue(target3.user == user)

        # both have user
        source_user = source4.user
        target_user = target4.user
        result = handle_users(source4, target4)
        self.assertTrue("DATATRACKER LOGIN ACTION: retaining login: {}, removing login: {}".format(target_user,source_user) in result)
        self.assertTrue(target4.user == target_user)
        self.assertTrue(source4.user == None)

    def test_get_extra_primary(self):
        source = PersonFactory()
        target = PersonFactory()
        extra = get_extra_primary(source, target)
        self.assertEqual(set(extra), set(source.email_set.filter(primary=True)))

    def test_dedupe_aliases(self):
        person = PersonFactory()
        Alias.objects.create(person=person, name='Joe')
        Alias.objects.create(person=person, name='Joe')
        self.assertEqual(person.alias_set.filter(name='Joe').count(),2)
        dedupe_aliases(person)
        self.assertEqual(person.alias_set.filter(name='Joe').count(),1)
      
    def test_merge_nominees(self):
        nomcom_test_data()
        nomcom = NomCom.objects.first()
        source = PersonFactory()
        source.nominee_set.create(nomcom=nomcom,email=source.email())
        target = PersonFactory()
        merge_nominees(source, target)
        self.assertTrue(target.nominee_set.all())

    def test_move_related_objects(self):
        source = PersonFactory()
        target = PersonFactory()
        source_email = source.email_set.first()
        source_alias = source.alias_set.first()
        move_related_objects(source, target, file=StringIO())
        self.assertTrue(source_email in target.email_set.all())
        self.assertTrue(source_alias in target.alias_set.all())

    def test_merge_persons(self):
        secretariat_role = RoleFactory(group__acronym='secretariat', name_id='secr')
        user = secretariat_role.person.user
        request = HttpRequest()
        request.user = user
        source = PersonFactory()
        source.uuids.create()  # give them an extra
        target = PersonFactory()
        mars = RoleFactory(name_id='chair',group__acronym='mars').group
        source_id = source.pk
        source_uuids = set(source.uuids.values_list("uuid", flat=True))
        target_uuids = set(target.uuids.values_list("uuid", flat=True))
        source_email = source.email_set.first()
        source_alias = source.alias_set.first()
        source_user = source.user
        communitylist = CommunityList.objects.create(person=source, group=mars)
        nomcom = NomComFactory()
        position = PositionFactory(nomcom=nomcom)
        nominee = NomineeFactory(nomcom=nomcom, person=mars.get_chair().person)
        feedback = FeedbackFactory(person=source, author=source.email().address, nomcom=nomcom)
        feedback.nominees.add(nominee)
        nomination = NominationFactory(nominee=nominee, person=source, position=position, comments=feedback)
        merge_persons(request, source, target, file=StringIO())
        self.assertTrue(source_email in target.email_set.all())
        self.assertTrue(source_alias in target.alias_set.all())
        self.assertIn(communitylist, target.communitylist_set.all())
        self.assertIn(feedback, target.feedback_set.all())
        self.assertIn(nomination, target.nomination_set.all())
        self.assertFalse(Person.objects.filter(id=source_id))
        self.assertFalse(source_user.is_active)
        self.assertEqual(
            set(target.uuids.values_list("uuid", flat=True)),
            source_uuids | target_uuids,
        )
        # The survivor keeps its own primary; the source's UUIDs become priors
        self.assertEqual(target.uuids.filter(primary=True).count(), 1)
        self.assertIn(target.primary_uuid, target_uuids)
        self.assertEqual(set(target.prior_uuids), source_uuids)

    def test_merge_persons_reviewer_settings(self):
        secretariat_role = RoleFactory(group__acronym='secretariat', name_id='secr')
        user = secretariat_role.person.user
        request = HttpRequest()
        request.user = user
        source = PersonFactory()
        target = PersonFactory()
        groups = Group.objects.all()
        ReviewerSettings.objects.create(team=groups[0],person=source,min_interval=14)
        ReviewerSettings.objects.create(team=groups[0],person=target,min_interval=7)
        merge_persons(request, source, target, file=StringIO())
        self.assertFalse(Person.objects.filter(pk=source.pk))
        self.assertEqual(target.reviewersettings_set.count(), 1)
        rs = target.reviewersettings_set.first()
        self.assertEqual(rs.min_interval, 7)

    def test_dots(self):
        noroles = PersonFactory()
        self.assertEqual(get_dots(noroles),[])
        wgchair = RoleFactory(name_id='chair',group__type_id='wg').person
        self.assertEqual(get_dots(wgchair),['chair'])
        ad = RoleFactory(name_id='ad',group__acronym='iesg').person
        self.assertEqual(get_dots(ad),['iesg'])
        iabmember = RoleFactory(name_id='member',group__acronym='iab').person
        self.assertEqual(get_dots(iabmember),['iab'])
        iabchair = RoleFactory(name_id='chair',group__acronym='iab').person
        RoleFactory(person=iabchair,group__acronym='iab',name_id='member')
        self.assertEqual(set(get_dots(iabchair)),set(['iab','iesg']))
        llcboard = RoleFactory(name_id='member',group__acronym='llc-board').person
        self.assertEqual(get_dots(llcboard),['llc'])
        ietftrust = RoleFactory(name_id='member',group__acronym='ietf-trust').person
        self.assertEqual(get_dots(ietftrust),['trust'])
        ncmember = RoleFactory(group__acronym='nomcom2020',group__type_id='nomcom',name_id='member').person
        self.assertEqual(get_dots(ncmember),['nomcom'])
        ncchair = RoleFactory(group__acronym='nomcom2020',group__type_id='nomcom',name_id='chair').person
        self.assertEqual(get_dots(ncchair),['nomcom'])

    def test_send_merge_request(self):
        empty_outbox()
        message_count_before = Message.objects.count()
        source = PersonFactory()
        target = PersonFactory()
        url = urlreverse('ietf.person.views.send_merge_request')
        url = url + f'?source={source.pk}&target={target.pk}'
        login_testing_unauthorized(self, 'secretary', url)
        r = self.client.get(url)
        initial = r.context['form'].initial
        subject = 'Action requested: Merging possible duplicate IETF Datatracker accounts'
        self.assertEqual(initial['to'], ', '.join([source.user.username, target.user.username]))
        self.assertEqual(initial['subject'], subject)
        self.assertEqual(initial['reply_to'], 'support@ietf.org')
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url, data=initial)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox), 1)
        self.assertIn(source.user.username, outbox[0]['To'])
        message_count_after = Message.objects.count()
        message = Message.objects.last()
        self.assertEqual(message_count_after, message_count_before + 1)
        self.assertIn(source.user.username, message.to)


class PersonUUIDTests(TestCase):
    def test_every_creation_path_assigns_a_primary(self):
        """Each production route that creates a Person gives it one primary UUID"""
        # ietf.ietfauth.views.confirm_account
        confirm_url = urlreverse(
            "ietf.ietfauth.views.confirm_account",
            kwargs={
                "auth": django.core.signing.dumps(
                    "uuidtest@example.com", salt="create_account"
                )
            },
        )
        self.client.post(
            confirm_url,
            {
                "name": "UUID Test",
                "ascii": "UUID Test",
                "password": "secret+password",
                "password_confirmation": "secret+password",
            },
        )
        created = Person.objects.get(name="UUID Test")
        self.assertEqual(created.uuids.filter(primary=True).count(), 1)

        # ietf.nomcom.utils.make_nomineeposition_for_newperson
        nomcom = NomComFactory(group__acronym="nomcom2021")
        position = PositionFactory(nomcom=nomcom)
        make_nomineeposition_for_newperson(
            nomcom,
            "New Nominee",
            "newnominee@example.com",
            position,
            PersonFactory().email(),
        )
        nominee_person = Person.objects.get(name="New Nominee")
        self.assertEqual(nominee_person.uuids.filter(primary=True).count(), 1)

        # ietf.submit.utils.ensure_person_email_info_exists
        ensure_person_email_info_exists(
            "Draft Author", "draftauthor@example.com", "draft-uuid-test"
        )
        author = Person.objects.get(name="Draft Author")
        self.assertEqual(author.uuids.filter(primary=True).count(), 1)

    def test_factory_assigns_a_primary(self):
        person = PersonFactory()
        self.assertEqual(person.uuids.filter(primary=True).count(), 1)
        self.assertIsNotNone(person.primary_uuid)
        self.assertEqual(person.prior_uuids, [])

    def test_assign_primary_uuid_is_idempotent(self):
        person = PersonFactory()
        first = person.primary_uuid
        assign_primary_uuid(person)
        self.assertEqual(person.uuids.count(), 1)
        self.assertEqual(person.primary_uuid, first)

    def test_only_one_primary_per_person(self):
        person = PersonFactory()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PersonUUID.objects.create(person=person, primary=True)

    def test_ensure_primary_uuid_promotes_earliest(self):
        person = PersonFactory()
        oldest = person.uuids.get()
        PersonUUID.objects.create(person=person, primary=False)
        person.uuids.update(primary=False)
        promoted = ensure_primary_uuid(person)
        self.assertEqual(promoted.uuid, oldest.uuid)
        self.assertEqual(person.uuids.filter(primary=True).count(), 1)

    def test_ensure_primary_uuid_creates_when_none(self):
        person = PersonFactory()
        person.uuids.all().delete()
        created = ensure_primary_uuid(person)
        self.assertTrue(created.primary)
        self.assertEqual(person.uuids.count(), 1)

    def test_get_person_uuid_object(self):
        person = PersonFactory()
        prior = PersonUUIDFactory(person=person)
        self.assertIsNone(get_person_uuid_object(uuid.uuid4()))
        primary_obj = get_person_uuid_object(person.primary_uuid)
        self.assertEqual(primary_obj.person, person)
        self.assertTrue(primary_obj.primary)
        prior_obj = get_person_uuid_object(prior.uuid)
        self.assertEqual(prior_obj.person, person)
        self.assertFalse(prior_obj.primary)

    def test_deleting_a_person_deletes_its_uuids(self):
        person = PersonFactory()
        values = list(person.uuids.values_list("uuid", flat=True))
        person.delete()
        self.assertEqual(PersonUUID.objects.filter(uuid__in=values).count(), 0)
        for value in values:
            self.assertIsNone(get_person_uuid_object(value))

    def test_merge_chain_keeps_one_primary(self):
        secretariat_role = RoleFactory(group__acronym="secretariat", name_id="secr")
        request = HttpRequest()
        request.user = secretariat_role.person.user
        a, b, c = PersonFactory.create_batch(3)
        a_uuids = set(a.uuids.values_list("uuid", flat=True))
        b_uuids = set(b.uuids.values_list("uuid", flat=True))
        c_primary = c.primary_uuid
        merge_persons(request, a, b, file=StringIO())
        merge_persons(request, b, c, file=StringIO())
        c.refresh_from_db()
        self.assertEqual(c.uuids.filter(primary=True).count(), 1)
        self.assertEqual(c.primary_uuid, c_primary)
        self.assertEqual(set(c.prior_uuids), a_uuids | b_uuids)
        for value in a_uuids | b_uuids:
            self.assertEqual(get_person_uuid_object(value).person, c)

    def test_merge_promotes_a_primary_for_a_target_without_one(self):
        secretariat_role = RoleFactory(group__acronym="secretariat", name_id="secr")
        request = HttpRequest()
        request.user = secretariat_role.person.user
        source = PersonFactory()
        target = PersonFactory()
        target.uuids.update(primary=False)
        merge_persons(request, source, target, file=StringIO())
        target.refresh_from_db()
        self.assertEqual(target.uuids.filter(primary=True).count(), 1)

    @mock.patch("ietf.person.utils.transaction.on_commit", side_effect=lambda f: f())
    @mock.patch("ietf.person.tasks.push_person_uuids_task.apply_async")
    def test_creating_a_person_does_not_push(self, mock_apply, mock_on_commit):
        # A brand-new Person has no Authentik account, so there is nothing to push to.
        person = PersonFactory()
        self.assertFalse(mock_apply.called)

        person.name = person.name + " Jr"
        person.save()
        self.assertFalse(mock_apply.called)  # nor does an unrelated save

    @mock.patch("ietf.person.utils.transaction.on_commit", side_effect=lambda f: f())
    @mock.patch("ietf.person.tasks.push_person_uuids_task.apply_async")
    def test_push_is_dispatched_when_the_set_changes(self, mock_apply, mock_on_commit):
        secretariat_role = RoleFactory(group__acronym="secretariat", name_id="secr")
        request = HttpRequest()
        request.user = secretariat_role.person.user
        source = PersonFactory()
        target = PersonFactory()
        mock_apply.reset_mock()

        merge_persons(request, source, target, file=StringIO())
        self.assertTrue(mock_apply.called)
        self.assertEqual(
            mock_apply.call_args.kwargs["kwargs"], {"person_pk": target.pk}
        )
        # Fire-and-forget: the reconcile job is the backstop, so a missing broker must
        # not stall the merge.
        self.assertFalse(mock_apply.call_args.kwargs["retry"])

        # Promoting a primary for a Person that already existed does push
        mock_apply.reset_mock()
        other = PersonFactory()
        other.uuids.update(primary=False)
        ensure_primary_uuid(other)
        self.assertEqual(mock_apply.call_args.kwargs["kwargs"], {"person_pk": other.pk})

    @mock.patch("ietf.person.utils.transaction.on_commit", side_effect=lambda f: f())
    @mock.patch("ietf.person.tasks.push_person_uuids_task.apply_async")
    @mock.patch("ietf.person.utils.log.log")
    def test_unreachable_broker_does_not_break_the_caller(
        self, mock_log, mock_apply, mock_on_commit
    ):
        mock_apply.side_effect = KombuOperationalError("no broker here")
        person = PersonFactory()
        person.uuids.update(primary=False)
        ensure_primary_uuid(person)  # must not raise
        self.assertEqual(person.uuids.filter(primary=True).count(), 1)
        self.assertIn("Could not queue UUID push", mock_log.call_args[0][0])

    @mock.patch("ietf.person.tasks.log.log")
    def test_push_person_uuids_task(self, mock_log):
        person = PersonFactory()
        prior = PersonUUIDFactory(person=person)
        push_person_uuids_task(person_pk=person.pk)
        message = mock_log.call_args[0][0]
        self.assertIn(str(person.primary_uuid), message)
        self.assertIn(str(prior.uuid), message)

        mock_log.reset_mock()
        push_person_uuids_task(person_pk=person.pk + 10000)
        self.assertIn("no such Person", mock_log.call_args[0][0])

    @mock.patch("ietf.person.tasks.log.log")
    def test_check_person_uuids_task(self, mock_log):
        good = PersonFactory()
        broken = PersonFactory()
        broken.uuids.all().delete()
        demoted = PersonFactory()
        demoted.uuids.update(primary=False)

        def logged():
            return "\n".join(call[0][0] for call in mock_log.call_args_list)

        self.assertEqual(check_person_uuids_task(), 2)
        report = logged()
        self.assertIn(f"Person {broken.pk}", report)
        self.assertIn("no UUIDs at all", report)
        self.assertIn(f"Person {demoted.pk}", report)
        self.assertIn("no primary UUID", report)
        self.assertNotIn(f"Person {good.pk} ", report)
        self.assertIn("2 Person(s) need attention", report)

        mock_log.reset_mock()
        self.assertEqual(check_person_uuids_task(fix=True), 2)
        self.assertIn("2 Person(s) repaired", logged())
        for person in (broken, demoted):
            self.assertEqual(person.uuids.filter(primary=True).count(), 1)

        mock_log.reset_mock()
        self.assertEqual(check_person_uuids_task(), 0)
        self.assertIn("every Person has exactly one primary UUID", logged())


@override_settings(
    APP_API_TOKENS={
        "ietf.person.api_uuid": ["uuid-api-token"],
        "ietf.person.api_uuid_by_pk": ["by-pk-token"],
    }
)
class PersonUUIDApiTests(TestCase):
    def retrieve_url(self, uuid_value):
        return urlreverse(
            "ietf.api.person_api.person-uuid-detail", kwargs={"uuid": uuid_value}
        )

    @property
    def lookup_url(self):
        return urlreverse("ietf.api.person_api.person-uuid-lookup")

    @property
    def by_pk_url(self):
        return urlreverse("ietf.api.person_api.person-uuid-by-pk")

    def test_requires_a_valid_api_key(self):
        person = PersonFactory()
        url = self.retrieve_url(person.primary_uuid)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.get(url, headers={"X-Api-Key": "nope"}).status_code, 403
        )
        self.assertEqual(
            self.client.get(url, headers={"X-Api-Key": "by-pk-token"}).status_code, 403
        )
        self.assertEqual(
            self.client.get(url, headers={"X-Api-Key": "uuid-api-token"}).status_code,
            200,
        )

    def test_retrieve_primary(self):
        person = PersonFactory()
        r = self.client.get(
            self.retrieve_url(person.primary_uuid),
            headers={"X-Api-Key": "uuid-api-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json(),
            {
                "uuid": str(person.primary_uuid),
                "is_primary": True,
                "primary_uuid": str(person.primary_uuid),
                "prior_uuids": [],
            },
        )

    def test_retrieve_superseded(self):
        person = PersonFactory()
        prior = PersonUUIDFactory(person=person)
        r = self.client.get(
            self.retrieve_url(prior.uuid), headers={"X-Api-Key": "uuid-api-token"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json(),
            {
                "uuid": str(prior.uuid),
                "is_primary": False,
                "primary_uuid": str(person.primary_uuid),
                "prior_uuids": [str(prior.uuid)],
            },
        )

    def test_response_carries_identifiers_only(self):
        person = PersonFactory()
        r = self.client.get(
            self.retrieve_url(person.primary_uuid),
            headers={"X-Api-Key": "uuid-api-token"},
        )
        self.assertEqual(
            set(r.json().keys()),
            {"uuid", "is_primary", "primary_uuid", "prior_uuids"},
        )

    def test_retrieve_unknown(self):
        r = self.client.get(
            self.retrieve_url(uuid.uuid4()), headers={"X-Api-Key": "uuid-api-token"}
        )
        self.assertEqual(r.status_code, 404)

    def test_retrieve_upper_case(self):
        person = PersonFactory()
        url = self.retrieve_url(person.primary_uuid)
        upper = url.replace(str(person.primary_uuid), str(person.primary_uuid).upper())
        self.assertNotEqual(url, upper)
        r = self.client.get(upper, headers={"X-Api-Key": "uuid-api-token"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["uuid"], str(person.primary_uuid))

    def test_retrieve_malformed(self):
        r = self.client.get(
            "/api/person/uuid/not-a-uuid/", headers={"X-Api-Key": "uuid-api-token"}
        )
        self.assertEqual(r.status_code, 404)

    def test_batch(self):
        person = PersonFactory()
        prior = PersonUUIDFactory(person=person)
        missing = uuid.uuid4()
        r = self.client.post(
            self.lookup_url,
            {
                "uuids": [
                    str(prior.uuid),
                    str(person.primary_uuid),
                    str(missing),
                    str(prior.uuid),
                ]
            },
            content_type="application/json",
            headers={"X-Api-Key": "uuid-api-token"},
        )
        self.assertEqual(r.status_code, 200)
        results = r.json()["results"]
        # One entry per distinct requested UUID, duplicates collapsed
        self.assertEqual(len(results), 3)
        by_uuid = {entry["uuid"]: entry for entry in results}
        # Same shape as a resolved entry, with the identifiers nulled out
        self.assertEqual(
            by_uuid[str(missing)],
            {
                "uuid": str(missing),
                "status": "unknown",
                "is_primary": None,
                "primary_uuid": None,
                "prior_uuids": [],
            },
        )
        self.assertEqual(by_uuid[str(prior.uuid)]["status"], "resolved")
        self.assertFalse(by_uuid[str(prior.uuid)]["is_primary"])
        self.assertEqual(
            by_uuid[str(prior.uuid)]["primary_uuid"], str(person.primary_uuid)
        )
        self.assertTrue(by_uuid[str(person.primary_uuid)]["is_primary"])

    def test_batch_query_count_is_independent_of_size(self):
        people = PersonFactory.create_batch(6)
        # Resolve the UUIDs up front so the capture below sees only the API's queries
        values = [str(p.primary_uuid) for p in people]

        def post(subset):
            return self.client.post(
                self.lookup_url,
                {"uuids": subset},
                content_type="application/json",
                headers={"X-Api-Key": "uuid-api-token"},
            )

        with CaptureQueriesContext(connection) as small:
            self.assertEqual(post(values[:2]).status_code, 200)
        with CaptureQueriesContext(connection) as large:
            self.assertEqual(post(values).status_code, 200)
        self.assertEqual(len(small.captured_queries), len(large.captured_queries))

    def test_batch_rejects_bad_input(self):
        for payload in (
            {"uuids": []},
            {"uuids": ["not-a-uuid"]},
            {"uuids": [str(uuid.uuid4()) for _ in range(501)]},
            {},
        ):
            r = self.client.post(
                self.lookup_url,
                payload,
                content_type="application/json",
                headers={"X-Api-Key": "uuid-api-token"},
            )
            self.assertEqual(r.status_code, 400, payload)

    def test_by_person_pk(self):
        person = PersonFactory()
        prior = PersonUUIDFactory(person=person)
        r = self.client.post(
            self.by_pk_url,
            {"person_pks": [person.pk, person.pk + 10000]},
            content_type="application/json",
            headers={"X-Api-Key": "by-pk-token"},
        )
        self.assertEqual(r.status_code, 200)
        results = r.json()["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(
            results[0],
            {
                "person_pk": person.pk,
                "status": "resolved",
                "primary_uuid": str(person.primary_uuid),
                "prior_uuids": [str(prior.uuid)],
            },
        )
        self.assertEqual(
            results[1],
            {
                "person_pk": person.pk + 10000,
                "status": "unknown",
                "primary_uuid": None,
                "prior_uuids": [],
            },
        )

    def test_by_person_pk_has_its_own_token(self):
        person = PersonFactory()
        r = self.client.post(
            self.by_pk_url,
            {"person_pks": [person.pk]},
            content_type="application/json",
            headers={"X-Api-Key": "uuid-api-token"},
        )
        self.assertEqual(r.status_code, 403)

    def test_by_person_pk_rejects_over_cap(self):
        r = self.client.post(
            self.by_pk_url,
            {"person_pks": list(range(501))},
            content_type="application/json",
            headers={"X-Api-Key": "by-pk-token"},
        )
        self.assertEqual(r.status_code, 400)

    def test_schema(self):
        r = self.client.get("/api/schema/")
        self.assertEqual(r.status_code, 200)
        schema = yaml.safe_load(r.content)
        paths = schema["paths"]
        self.assertIn("/api/person/uuid/{uuid}/", paths)
        self.assertIn("/api/person/uuid/lookup/", paths)
        self.assertIn("/api/person/uuid/by-person-pk/", paths)
        self.assertEqual(
            paths["/api/person/uuid/{uuid}/"]["get"]["operationId"],
            "person_uuid_retrieve",
        )
        self.assertEqual(
            paths["/api/person/uuid/lookup/"]["post"]["operationId"],
            "person_uuid_lookup",
        )
        by_pk = paths["/api/person/uuid/by-person-pk/"]["post"]
        self.assertEqual(by_pk["operationId"], "person_uuid_by_person_pk")
        self.assertTrue(by_pk["deprecated"])
        self.assertIn("PersonUUIDResolution", schema["components"]["schemas"])
        # The declared success codes have to be the ones the views actually return -
        # nothing here creates anything, so nothing may advertise a 201.
        for path, method in (
            ("/api/person/uuid/{uuid}/", "get"),
            ("/api/person/uuid/lookup/", "post"),
            ("/api/person/uuid/by-person-pk/", "post"),
        ):
            responses = paths[path][method]["responses"]
            self.assertIn("200", responses, path)
            self.assertNotIn("201", responses, path)
        # Consumers switch on status, so it has to be a declared, required field
        for component in ("PersonUUIDBatchEntry", "PersonPkBatchEntry"):
            entry = schema["components"]["schemas"][component]
            self.assertIn("status", entry["required"], component)
            self.assertTrue(entry["properties"]["primary_uuid"]["nullable"], component)


class TaskTests(TestCase):
    @mock.patch("ietf.person.tasks.log.log")
    def test_purge_personal_api_key_events_task(self, mock_log):
        now = timezone.now()
        old_event = PersonApiKeyEventFactory(time=now - datetime.timedelta(days=1, minutes=1))
        young_event = PersonApiKeyEventFactory(time=now - datetime.timedelta(days=1, minutes=-1))
        purge_personal_api_key_events_task(keep_days=1)
        self.assertFalse(PersonApiKeyEvent.objects.filter(pk=old_event.pk).exists())
        self.assertTrue(PersonApiKeyEvent.objects.filter(pk=young_event.pk).exists())
        self.assertTrue(mock_log.called)
        self.assertIn("Deleted 1", mock_log.call_args[0][0])
