# Copyright The IETF Trust 2014-2022, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import json
import mock

from io import StringIO, BytesIO
from PIL import Image
from pyquery import PyQuery


from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.test import override_settings
from django.urls import reverse as urlreverse
from django.utils import timezone
from django.utils.encoding import iri_to_uri

import debug                            # pyflakes:ignore

from ietf.community.models import CommunityList
from ietf.group.factories import RoleFactory
from ietf.group.models import Group
from ietf.nomcom.models import NomCom
from ietf.nomcom.test_data import nomcom_test_data
from ietf.nomcom.factories import NomComFactory, NomineeFactory, NominationFactory, FeedbackFactory, PositionFactory
from ietf.person.factories import EmailFactory, PersonFactory, PersonApiKeyEventFactory
from ietf.person.models import Person, Alias, PersonApiKeyEvent
from ietf.person.tasks import purge_personal_api_key_events_task
from ietf.person.utils import (merge_persons, determine_merge_order, send_merge_notification,
    handle_users, get_extra_primary, dedupe_aliases, move_related_objects, merge_nominees,
    handle_reviewer_settings, get_dots)
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
        primary = EmailFactory(person=person, primary=True, active=True)
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
        url = urlreverse("ietf.person.views.merge") + "?source={}&target={}".format(p1.pk, p2.pk)
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertContains(r, 'retaining login', status_code=200)

    def test_merge_with_params_bad_id(self):
        url = urlreverse("ietf.person.views.merge") + "?source=1000&target=2000"
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertContains(r, 'ID does not exist', status_code=200)

    def test_merge_post(self):
        p1 = get_person_no_user()
        p2 = PersonFactory()
        url = urlreverse("ietf.person.views.merge")
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
        self.assertTrue(extra == list(source.email_set.filter(primary=True)))

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
        target = PersonFactory()
        mars = RoleFactory(name_id='chair',group__acronym='mars').group
        source_id = source.pk
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
