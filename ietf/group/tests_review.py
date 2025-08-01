# Copyright The IETF Trust 2016-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import debug      # pyflakes:ignore

from pyquery import PyQuery

from django.conf import settings
from django.urls import reverse as urlreverse
from django.utils import timezone

from ietf.review.policies import get_reviewer_queue_policy
from ietf.utils.test_utils import login_testing_unauthorized, TestCase, reload_db_objects
from ietf.doc.models import TelechatDocEvent, LastCallDocEvent, State
from ietf.iesg.models import TelechatDate
from ietf.person.models import Person
from ietf.review.models import ReviewerSettings, UnavailablePeriod, ReviewSecretarySettings,NextReviewerInTeam
from ietf.review.utils import suggested_review_requests_for_team
from ietf.name.models import ReviewResultName, ReviewRequestStateName, ReviewAssignmentStateName, \
    ReviewTypeName
import ietf.group.views
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.dbtemplate.factories import DBTemplateFactory
from ietf.person.factories import PersonFactory, EmailFactory
from ietf.doc.factories import DocumentFactory
from ietf.group.factories import RoleFactory, ReviewTeamFactory, GroupFactory
from ietf.review.factories import ReviewRequestFactory, ReviewerSettingsFactory, ReviewAssignmentFactory
from ietf.utils.timezone import date_today, datetime_today, DEADLINE_TZINFO
from django.utils.html import escape

class ReviewTests(TestCase):
    def test_review_requests(self):
        review_req = ReviewRequestFactory(state_id='assigned')
        assignment = ReviewAssignmentFactory(review_request=review_req, state_id='assigned', reviewer=EmailFactory(), assigned_on = review_req.time)
        group = review_req.team

        for url in [urlreverse(ietf.group.views.review_requests, kwargs={ 'acronym': group.acronym }),
                    urlreverse(ietf.group.views.review_requests, kwargs={ 'acronym': group.acronym , 'group_type': group.type_id})]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, review_req.doc.name)
            self.assertContains(r, escape(assignment.reviewer.person.name))

        url = urlreverse(ietf.group.views.review_requests, kwargs={ 'acronym': group.acronym })

        # close request, listed under closed
        review_req.state = ReviewRequestStateName.objects.get(slug="completed")
        review_req.result = ReviewResultName.objects.get(slug="ready")
        review_req.save()

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, review_req.doc.name)

    def test_suggested_review_requests(self):
        review_req = ReviewRequestFactory(state_id='assigned')
        assignment = ReviewAssignmentFactory(review_request=review_req, state_id='assigned')
        doc = review_req.doc
        team = review_req.team

        # put on telechat
        e = TelechatDocEvent.objects.create(
            type="scheduled_for_telechat",
            by=Person.objects.get(name="(System)"),
            doc=doc,
            rev=doc.rev,
            telechat_date=TelechatDate.objects.all().first().date,
        )
        doc.rev = "10"
        doc.save_with_history([e])

        prev_rev = "{:02}".format(int(doc.rev) - 1)

        # blocked by existing request
        review_req.requested_rev = ""
        review_req.save()

        self.assertEqual(len(suggested_review_requests_for_team(team)), 0)

        # ... but not to previous version
        review_req.requested_rev = prev_rev
        review_req.save()
        suggestions = suggested_review_requests_for_team(team)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].doc, doc)
        self.assertEqual(suggestions[0].team, team)
        self.assertFalse(getattr(suggestions[0], 'in_lc_and_telechat', None))

        # blocked by non-versioned refusal
        review_req.requested_rev = ""
        review_req.state = ReviewRequestStateName.objects.get(slug="no-review-document")
        review_req.save()

        self.assertEqual(list(suggested_review_requests_for_team(team)), [])

        # blocked by versioned refusal
        review_req.state = ReviewRequestStateName.objects.get(slug="no-review-version")
        review_req.save()

        self.assertEqual(list(suggested_review_requests_for_team(team)), [])

        # blocked by an already existing request (don't suggest it again)
        review_req.state_id = "requested"
        review_req.save()
        self.assertEqual(list(suggested_review_requests_for_team(team)), [])

        # ... but not for a previous version
        review_req.requested_rev = prev_rev
        review_req.save()
        self.assertEqual(len(suggested_review_requests_for_team(team)), 1)


        # blocked by completion
        review_req.state = ReviewRequestStateName.objects.get(slug="assigned")
        review_req.requested_rev = ""
        review_req.save()
        assignment.state = ReviewAssignmentStateName.objects.get(slug="completed")
        assignment.reviewed_rev = review_req.doc.rev
        assignment.save()

        self.assertEqual(list(suggested_review_requests_for_team(team)), [])

        # ... but not to previous version
        assignment.reviewed_rev = prev_rev
        assignment.save()

        self.assertEqual(len(suggested_review_requests_for_team(team)), 1)


    def test_suggested_review_requests_on_lc_and_telechat(self):
        review_req = ReviewRequestFactory(state_id='assigned')
        doc = review_req.doc
        team = review_req.team

        # put on telechat
        TelechatDocEvent.objects.create(
            type="scheduled_for_telechat",
            by=Person.objects.get(name="(System)"),
            doc=doc,
            rev=doc.rev,
            telechat_date=TelechatDate.objects.all().first().date,
        )

        # Put on last call as well
        doc.states.add(State.objects.get(type="draft-iesg", slug="lc", used=True))
        LastCallDocEvent.objects.create(
            doc=doc,
            expires=timezone.now() + datetime.timedelta(days=365),
            by=Person.objects.get(name="(System)"),
            rev=doc.rev
        )

        suggestions = suggested_review_requests_for_team(team)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].doc, doc)
        self.assertEqual(suggestions[0].team, team)
        self.assertTrue(suggestions[0].in_lc_and_telechat)

    def test_reviewer_overview(self):
        team = ReviewTeamFactory()
        reviewer = RoleFactory(name_id='reviewer',group=team,person__user__username='reviewer').person
        ReviewerSettingsFactory(person=reviewer,team=team)
        review_req1 = ReviewRequestFactory(state_id='completed',team=team)
        secretary = Person.objects.get(user__username="secretary")
        ReviewAssignmentFactory(review_request = review_req1, reviewer=reviewer.email())
        PersonFactory(user__username='plain')

        ReviewAssignmentFactory(
            review_request__doc=review_req1.doc,
            review_request__team=review_req1.team,
            review_request__type_id="early",
            review_request__deadline=date_today(DEADLINE_TZINFO) + datetime.timedelta(days=30),
            review_request__state_id="assigned",
            review_request__requested_by=Person.objects.get(user__username="reviewer"),
            state_id = "accepted",
            reviewer=reviewer.email_set.first(),
        )

        UnavailablePeriod.objects.create(
            team=review_req1.team,
            person=reviewer,
            start_date=date_today() - datetime.timedelta(days=10),
            availability="unavailable",
        )

        settings = ReviewerSettings.objects.get(person=reviewer,team=review_req1.team)
        settings.skip_next = 1
        settings.save()

        group = review_req1.team

        # get
        for url in [urlreverse(ietf.group.views.reviewer_overview, kwargs={ 'acronym': group.acronym }),
                    urlreverse(ietf.group.views.reviewer_overview, kwargs={ 'acronym': group.acronym, 'group_type': group.type_id })]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, escape(reviewer.name))
            self.assertContains(r, review_req1.doc.name)
            # without a login, reason for being unavailable should not be seen
            self.assertNotContains(r, "Availability")

        url = urlreverse(ietf.group.views.reviewer_overview, kwargs={ 'acronym': group.acronym })
        self.client.login(username="plain", password="plain+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # not on review team, should not see reason for being unavailable
        self.assertNotContains(r, "Availability")

        self.client.login(username="reviewer", password="reviewer+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # review team members can see reason for being unavailable
        self.assertContains(r, "Available")

        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # secretariat can see reason for being unavailable
        self.assertContains(r, "Available")

        # add one closed review with no response and see it is visible
        review_req2 = ReviewRequestFactory(state_id='completed',team=team)
        ReviewAssignmentFactory(
            review_request__doc=review_req2.doc,
            review_request__team=review_req2.team,
            review_request__type_id="lc",
            review_request__deadline=date_today(DEADLINE_TZINFO) - datetime.timedelta(days=30),
            review_request__state_id="assigned",
            review_request__requested_by=Person.objects.get(user__username="reviewer"),
            state_id = "no-response",
            reviewer=reviewer.email_set.first(),
        )
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # We should see the new document with status of no response
        self.assertContains(r, "No response")
        self.assertContains(r, review_req1.doc.name)
        self.assertContains(r, review_req2.doc.name)
        # None of the reviews should be completed this time,
        # note that "Days Since Completed has soft hyphens in it, so it
        # will not match
        self.assertNotContains(r, "Completed")
        # add multiple completed reviews
        review_req3 = ReviewRequestFactory(state_id='completed', team=team)
        ReviewAssignmentFactory(
            review_request__doc=review_req3.doc,
            review_request__time=datetime_today() - datetime.timedelta(days=30),
            review_request__team=review_req3.team,
            review_request__type_id="telechat",
            review_request__deadline=date_today(DEADLINE_TZINFO) - datetime.timedelta(days=25),
            review_request__state_id="completed",
            review_request__requested_by=Person.objects.get(user__username="reviewer"),
            state_id = "completed",
            reviewer=reviewer.email_set.first(),
            assigned_on=datetime_today() - datetime.timedelta(days=30)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Completed")
        self.assertContains(r, review_req1.doc.name)
        self.assertContains(r, review_req2.doc.name)
        self.assertContains(r, review_req3.doc.name)
        # Few more to make sure we hit the limit
        reqs = [ReviewRequestFactory(state_id='completed', team=team) for i in range(10)]
        for i in range(10):
            ReviewAssignmentFactory(
                review_request__doc=reqs[i].doc,
                review_request__time=datetime_today() - datetime.timedelta(days=i*30),
                review_request__team=reqs[i].team,
                review_request__type_id="telechat",
                review_request__deadline=date_today(DEADLINE_TZINFO) - datetime.timedelta(days=i*20),
                review_request__state_id="completed",
                review_request__requested_by=Person.objects.get(user__username="reviewer"),
                state_id = "completed",
                reviewer=reviewer.email_set.first(),
                assigned_on=datetime_today() - datetime.timedelta(days=i*30)
            )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Completed")
        self.assertContains(r, review_req1.doc.name)
        self.assertContains(r, review_req2.doc.name)
        self.assertContains(r, review_req3.doc.name)
        # The default is 10 completed entries, we had one before + one No response
        # so we should have 8 more here
        for i in range(10):
            if i < 8:
                self.assertContains(r, reqs[i].doc.name)
            else:
                self.assertNotContains(r, reqs[i].doc.name)
        # Change the limit to be 15 instead of 10, so we should get all
        secretary_settings = ReviewSecretarySettings(team=team, person=secretary)
        secretary_settings.max_items_to_show_in_reviewer_list = 15
        secretary_settings.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, review_req1.doc.name)
        self.assertContains(r, review_req2.doc.name)
        self.assertContains(r, review_req3.doc.name)
        for i in range(10):
            self.assertContains(r, reqs[i].doc.name)
        # Change the time limit to 100 days, so we should only get 3 completed
        secretary_settings.days_to_show_in_reviewer_list = 100
        secretary_settings.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, review_req1.doc.name)
        self.assertContains(r, review_req2.doc.name)
        self.assertContains(r, review_req3.doc.name)
        for i in range(10):
            if i < 4:
                self.assertContains(r, reqs[i].doc.name)
            else:
                self.assertNotContains(r, reqs[i].doc.name)
        # Add assigned items, they should be visible as long as they
        # are within time period
        review_req4 = ReviewRequestFactory(state_id='completed', team=team)
        ReviewAssignmentFactory(
            review_request__doc=review_req4.doc,
            review_request__time=datetime_today() - datetime.timedelta(days=80),
            review_request__team=review_req4.team,
            review_request__type_id="lc",
            review_request__deadline=date_today(DEADLINE_TZINFO) - datetime.timedelta(days=60),
            review_request__state_id="assigned",
            review_request__requested_by=Person.objects.get(user__username="reviewer"),
            state_id = "accepted",
            reviewer=reviewer.email_set.first(),
            assigned_on=datetime_today() - datetime.timedelta(days=80)
        )
        review_req5 = ReviewRequestFactory(state_id='completed', team=team)
        ReviewAssignmentFactory(
            review_request__doc=review_req5.doc,
            review_request__time=datetime_today() - datetime.timedelta(days=120),
            review_request__team=review_req5.team,
            review_request__type_id="lc",
            review_request__deadline=date_today(DEADLINE_TZINFO) - datetime.timedelta(days=100),
            review_request__state_id="assigned",
            review_request__requested_by=Person.objects.get(user__username="reviewer"),
            state_id = "accepted",
            reviewer=reviewer.email_set.first(),
            assigned_on=datetime_today() - datetime.timedelta(days=120)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, review_req1.doc.name)
        self.assertContains(r, review_req2.doc.name)
        self.assertContains(r, review_req3.doc.name)
        self.assertContains(r, review_req4.doc.name)
        self.assertNotContains(r, review_req5.doc.name)
        for i in range(10):
            if i < 4:
                self.assertContains(r, reqs[i].doc.name)
            else:
                self.assertNotContains(r, reqs[i].doc.name)
        # Change the limit to be 1 instead of 10, so we should only one entry
        secretary_settings.max_items_to_show_in_reviewer_list = 1
        secretary_settings.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, review_req1.doc.name)
        self.assertContains(r, review_req2.doc.name)
        self.assertNotContains(r, review_req3.doc.name)
        for i in range(10):
            self.assertNotContains(r, reqs[i].doc.name)
        self.assertContains(r, review_req4.doc.name)
        self.assertNotContains(r, review_req5.doc.name)

    def test_manage_review_requests(self):
        group = ReviewTeamFactory()
        RoleFactory(name_id='reviewer',group=group,person__user__username='reviewer').person
        marsperson = RoleFactory(name_id='reviewer',group=group,person=PersonFactory(name="Mars Anders Chairman",user__username='marschairman')).person
        doc_author = PersonFactory()
        review_req1 = ReviewRequestFactory(doc__pages=2,doc__shepherd=marsperson.email(),team=group, doc__authors=[doc_author])
        review_req2 = ReviewRequestFactory(team=group)
        review_req3 = ReviewRequestFactory(team=group)
        RoleFactory(name_id='chair',group=review_req1.doc.group,person=marsperson)

        unassigned_url = urlreverse(ietf.group.views.manage_review_requests, kwargs={ 'acronym': group.acronym, 'group_type': group.type_id, "assignment_status": "unassigned" })
        login_testing_unauthorized(self, "secretary", unassigned_url)

        # Need one more person in review team one so we can test incrementing skip_count without immediately decrementing it
        another_reviewer = PersonFactory.create(name = "Extra TestReviewer") # needs to be lexically greater than the existing one
        another_reviewer.role_set.create(name_id='reviewer', email=another_reviewer.email(), group=review_req1.team)
        ReviewerSettingsFactory(team=review_req3.team, person = another_reviewer)
        yet_another_reviewer = PersonFactory.create(name = "YetAnotherExtra TestReviewer") # needs to be lexically greater than the existing one
        yet_another_reviewer.role_set.create(name_id='reviewer', email=yet_another_reviewer.email(), group=review_req1.team)
        ReviewerSettingsFactory(team=review_req3.team, person = yet_another_reviewer)

        # get
        r = self.client.get(unassigned_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, escape(review_req1.doc.name))
        self.assertContains(r, escape(doc_author.name))

        # Test that conflicts are detected
        r = self.client.post(unassigned_url, {
            "reviewrequest": [str(review_req3.pk)],

            "r{}-existing_reviewer".format(review_req3.pk): "",
            "r{}-action".format(review_req3.pk): "assign",
            "r{}-reviewer".format(review_req3.pk): another_reviewer.email_set.first().pk,
            "r{}-add_skip".format(review_req3.pk): 1,
            
            "action": "save",
        })
        self.assertContains(r, "2 requests opened")

        r = self.client.post(unassigned_url, {
            "reviewrequest": [str(review_req1.pk),str(review_req2.pk),str(review_req3.pk)],

            "r{}-existing_reviewer".format(review_req3.pk): "",
            "r{}-action".format(review_req3.pk): "assign",
            "r{}-reviewer".format(review_req3.pk): another_reviewer.email_set.first().pk,
            "r{}-add_skip".format(review_req3.pk): 1,
            # Should be ignored, setting review_type only applies to suggested reviews
            "r{}-review_type".format(review_req3.pk): ReviewTypeName.objects.get(slug='telechat').pk,

            "action": "save",
        })
        self.assertEqual(r.status_code, 302)

        review_req3 = reload_db_objects(review_req3)
        settings = ReviewerSettings.objects.filter(team=review_req3.team, person=another_reviewer).first()
        self.assertEqual(settings.skip_next,1)
        self.assertEqual(review_req3.state_id, "assigned")
        self.assertEqual(review_req3.type_id, "lc")

    def test_manage_review_requests_assign_suggested_reviews(self):
        doc = DocumentFactory()
        team = ReviewTeamFactory()

        # put on telechat
        TelechatDocEvent.objects.create(
            type="scheduled_for_telechat",
            by=Person.objects.get(name="(System)"),
            doc=doc,
            rev=doc.rev,
            telechat_date=TelechatDate.objects.all().first().date,
        )

        # Put on last call as well
        doc.states.add(State.objects.get(type="draft-iesg", slug="lc", used=True))
        LastCallDocEvent.objects.create(
            doc=doc,
            expires=timezone.now() + datetime.timedelta(days=365),
            by=Person.objects.get(name="(System)"),
            rev=doc.rev
        )

        reviewer = RoleFactory(name_id='reviewer', group=team, person__user__username='reviewer')
        unassigned_url = urlreverse(ietf.group.views.manage_review_requests, kwargs={ 'acronym': team.acronym, 'group_type': team.type_id, "assignment_status": "unassigned" })

        login_testing_unauthorized(self, "secretary", unassigned_url)

        # get
        r = self.client.get(unassigned_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, doc.name)

        # Submit as lc review
        r = self.client.post(unassigned_url, {
            "rlc-{}-action".format(doc.name): "assign",
            "rlc-{}-review_type".format(doc.name): ReviewTypeName.objects.get(slug='lc').pk,
            "rlc-{}-reviewer".format(doc.name): reviewer.person.email_set.first().pk,

            "action": "save",
        })
        self.assertEqual(r.status_code, 302)
        review_request = doc.reviewrequest_set.get()
        self.assertEqual(review_request.type_id, 'lc')
        
        # Clean up and try again as telechat
        review_request.reviewassignment_set.all().delete()
        review_request.delete()
        
        r = self.client.post(unassigned_url, {
            "rlc-{}-action".format(doc.name): "assign",
            "rlc-{}-review_type".format(doc.name): ReviewTypeName.objects.get(slug='telechat').pk,
            "rlc-{}-reviewer".format(doc.name): reviewer.person.email_set.first().pk,

            "action": "save",
        })
        self.assertEqual(r.status_code, 302)
        review_request = doc.reviewrequest_set.get()
        self.assertEqual(review_request.type_id, 'telechat')
        
    def test_email_open_review_assignments(self):
        review_req1 = ReviewRequestFactory()
        review_assignment_completed = ReviewAssignmentFactory(review_request=review_req1,reviewer=EmailFactory(person__user__username='marschairman'), state_id='completed', reviewed_rev=0)
        ReviewAssignmentFactory(review_request=review_req1,reviewer=review_assignment_completed.reviewer)
        TelechatDocEvent.objects.create(telechat_date=date_today(settings.TIME_ZONE), type='scheduled_for_telechat', by=review_assignment_completed.reviewer.person, doc=review_req1.doc, rev=0)

        DBTemplateFactory.create(path='/group/defaults/email/open_assignments.txt',
                                 type_id='django',
                                 content = """
                                        {% autoescape off %}Subject: Open review assignments in {{group.acronym}}

                                        The following reviewers have assignments:{% for r in review_assignments %}{% ifchanged r.section %}
                                        
                                        {{r.section}}
                                        
                                        {% if r.section == 'Early review requests:' %}Reviewer               Due        Draft{% else %}Reviewer               LC end     Draft{% endif %}{% endifchanged %}
                                        {{ r.reviewer.person.plain_name|ljust:"22" }} {% if r.section == 'Early review requests:' %}{{ r.review_request.deadline|date:"Y-m-d" }}{% else %}{{ r.lastcall_ends|default:"None      " }}{% endif %} {{ r.review_request.doc.name }}-{% if r.review_request.requested_rev %}{{ r.review_request.requested_rev }}{% else %}{{ r.review_request..doc.rev }}{% endif %} {{ r.earlier_reviews }}{% endfor %}
                                        
                                        {% if rotation_list %}Next in the reviewer rotation:
                                        
                                        {% for p in rotation_list %}  {{ p }}
                                        {% endfor %}{% endif %}{% endautoescape %}
                                 """)

        group = review_req1.team

        url = urlreverse(ietf.group.views.email_open_review_assignments, kwargs={ 'acronym': group.acronym })

        login_testing_unauthorized(self, "secretary", url)

        url = urlreverse(ietf.group.views.email_open_review_assignments, kwargs={ 'acronym': group.acronym, 'group_type': group.type_id })

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        generated_text = q("[name=body]").text()
        # The document should be listed both for the telechat, and in the last call section,
        # i.e. the document name is expected twice in the output (#2118)
        self.assertEqual(generated_text.count(review_req1.doc.name), 2)
        self.assertEqual(generated_text.count('(-0 lc reviewed)'), 2)  # previous completed assignment
        self.assertTrue(str(Person.objects.get(user__username="marschairman")) in generated_text)

        empty_outbox()
        r = self.client.post(url, {
            "to": 'toaddr@bogus.test',
            "cc": 'ccaddr@bogus.test',
            "reply_to": 'replytoaddr@bogus.test',
            "frm" : 'fromaddr@bogus.test',
            "subject": "Test subject",
            "body": "Test body",
            "action": "email",
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox), 1)
        self.assertIn('toaddr', outbox[0]["To"])
        self.assertIn('ccaddr', outbox[0]["Cc"])
        self.assertIn('replytoaddr', outbox[0]["Reply-To"])
        self.assertIn('fromaddr', outbox[0]["From"])
        self.assertEqual(outbox[0]["subject"], "Test subject")
        self.assertIn("Test body", get_payload_text(outbox[0]))

    def test_change_reviewer_settings(self):
        reviewer = ReviewerSettingsFactory(person__user__username='reviewer',expertise='Some expertise').person
        review_req = ReviewRequestFactory()
        assignment = ReviewAssignmentFactory(review_request=review_req,reviewer=reviewer.email())
        RoleFactory(name_id='reviewer',group=review_req.team,person=assignment.reviewer.person)
        RoleFactory(name_id='secr',group=review_req.team)

        url = urlreverse(ietf.group.views.change_reviewer_settings, kwargs={
            "acronym": review_req.team.acronym,
            "reviewer_email": assignment.reviewer_id,
        })

        login_testing_unauthorized(self, reviewer.user.username, url)

        url = urlreverse(ietf.group.views.change_reviewer_settings, kwargs={
            "group_type": review_req.team.type_id,
            "acronym": review_req.team.acronym,
            "reviewer_email": assignment.reviewer_id,
        })

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['period_form']['start_date'].initial, date_today())

        # set settings
        empty_outbox()
        r = self.client.post(url, {
            "action": "change_settings",
            "min_interval": "7",
            "filter_re": "test-[regexp]",
            "remind_days_before_deadline": "6",
            "remind_days_open_reviews": "8",
            "request_assignment_next": "1",
            "expertise": "Some expertise",
        })
        self.assertEqual(r.status_code, 302)
        settings = ReviewerSettings.objects.get(person=reviewer, team=review_req.team)
        self.assertEqual(settings.min_interval, 7)
        self.assertEqual(settings.filter_re, "test-[regexp]")
        self.assertEqual(settings.skip_next, 0)
        self.assertEqual(settings.remind_days_before_deadline, 6)
        self.assertEqual(settings.remind_days_open_reviews, 8)
        self.assertEqual(settings.expertise, "Some expertise")
        self.assertEqual(len(outbox), 1)
        self.assertTrue("reviewer availability" in outbox[0]["subject"].lower())
        msg_content = get_payload_text(outbox[0])
        self.assertTrue("Frequency changed", msg_content)
        self.assertTrue("Skip next", msg_content)
        self.assertTrue("requested to be the next person", msg_content)

        # Normal reviewer should not be able to change skip_next
        r = self.client.post(url, {
            "action": "change_settings",
            "min_interval": "7",
            "filter_re": "test-[regexp]",
            "remind_days_before_deadline": "6",
            "skip_next" : "2",
        })
        self.assertEqual(r.status_code, 302)
        settings = ReviewerSettings.objects.get(person=reviewer, team=review_req.team)
        self.assertEqual(settings.skip_next, 0)

        # add unavailable period
        start_date = date_today() + datetime.timedelta(days=10)
        empty_outbox()
        r = self.client.post(url, {
            "action": "add_period",
            'start_date': start_date.isoformat(),
            'end_date': "",
            'availability': "unavailable",
            'reason': "Whimsy",
        })
        self.assertEqual(r.status_code, 302)
        period = UnavailablePeriod.objects.get(person=reviewer, team=review_req.team, start_date=start_date)
        self.assertEqual(period.end_date, None)
        self.assertEqual(period.availability, "unavailable")
        self.assertEqual(len(outbox), 1)
        msg_content = get_payload_text(outbox[0])
        self.assertTrue(start_date.isoformat(), msg_content)
        self.assertTrue("indefinite", msg_content)
        self.assertTrue("Whimsy", msg_content)
        self.assertEqual(period.reason, "Whimsy")

        # end unavailable period
        empty_outbox()
        end_date = start_date + datetime.timedelta(days=10)
        r = self.client.post(url, {
            "action": "end_period",
            'period_id': period.pk,
            'end_date': end_date.isoformat(),
        })
        self.assertEqual(r.status_code, 302)
        period = reload_db_objects(period)
        self.assertEqual(period.end_date, end_date)
        self.assertEqual(len(outbox), 1)
        msg_content = get_payload_text(outbox[0])
        self.assertTrue('Set end date', msg_content)
        self.assertTrue(start_date.isoformat(), msg_content)
        self.assertTrue(end_date.isoformat(), msg_content)
        self.assertTrue("indefinite", msg_content)

        # delete unavailable period
        empty_outbox()
        r = self.client.post(url, {
            "action": "delete_period",
            'period_id': period.pk,
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(UnavailablePeriod.objects.filter(person=reviewer, team=review_req.team, start_date=start_date).count(), 0)
        self.assertEqual(len(outbox), 1)
        msg_content = get_payload_text(outbox[0])
        self.assertTrue('Removed', msg_content)
        self.assertTrue(start_date.isoformat(), msg_content)
        self.assertTrue(end_date.isoformat(), msg_content)

        # secretaries and the secretariat should be able to change skip_next
        for username in ["secretary","reviewsecretary"]:
            skip_next_val = {'secretary':'3','reviewsecretary':'4'}[username]
            self.client.login(username=username,password=username+"+password")
            r = self.client.post(url, {
                "action": "change_settings",
                "min_interval": "7",
                "filter_re": "test-[regexp]",
                "remind_days_before_deadline": "6",
                "skip_next" : skip_next_val,
            })
            self.assertEqual(r.status_code, 302)
            settings = ReviewerSettings.objects.get(person=reviewer, team=review_req.team)
            self.assertEqual(settings.skip_next, int(skip_next_val))
            

    def test_change_review_secretary_settings(self):
        review_req = ReviewRequestFactory()
        secretary = RoleFactory(name_id='secr',group=review_req.team,person__user__username='reviewsecretary').person

        url = urlreverse(ietf.group.views.change_review_secretary_settings, kwargs={
            "acronym": review_req.team.acronym,
        })

        login_testing_unauthorized(self, secretary.user.username, url)

        url = urlreverse(ietf.group.views.change_review_secretary_settings, kwargs={
            "group_type": review_req.team.type_id,
            "acronym": review_req.team.acronym,
        })

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # set settings
        r = self.client.post(url, {
            "remind_days_before_deadline": "6",
            "max_items_to_show_in_reviewer_list": 10,
            "days_to_show_in_reviewer_list": 365
        })
        self.assertEqual(r.status_code, 302)
        settings = ReviewSecretarySettings.objects.get(person=secretary, team=review_req.team)
        self.assertEqual(settings.remind_days_before_deadline, 6)
        self.assertEqual(settings.max_items_to_show_in_reviewer_list, 10)
        self.assertEqual(settings.days_to_show_in_reviewer_list, 365)

    def test_assign_reviewer_after_reject(self):
        team = ReviewTeamFactory()
        reviewer = RoleFactory(name_id='reviewer', group=team).person
        ReviewerSettingsFactory(person=reviewer, team=team)
        review_req = ReviewRequestFactory(team=team)
        ReviewAssignmentFactory(review_request=review_req, state_id='rejected', reviewer=reviewer.email())

        unassigned_url = urlreverse(ietf.group.views.manage_review_requests, kwargs={ 'acronym': team.acronym, 'group_type': team.type_id, "assignment_status": "unassigned" })
        login_testing_unauthorized(self, "secretary", unassigned_url)

        r = self.client.get(unassigned_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        reviewer_label = q("option[value=\"{}\"]".format(reviewer.email())).text().lower()
        self.assertIn("rejected review of document before", reviewer_label)


class BulkAssignmentTests(TestCase):

    def test_rotation_queue_update(self):
        group = ReviewTeamFactory.create()
        empty_outbox()
        reviewers = [RoleFactory.create(group=group,name_id='reviewer') for i in range(6)] # pyflakes:ignore
        secretary = RoleFactory.create(group=group,name_id='secr')
        docs = [DocumentFactory.create(type_id='draft',group=None) for i in range(4)]
        requests = [ReviewRequestFactory(team=group,doc=docs[i]) for i in range(4)]
        policy = get_reviewer_queue_policy(group)
        rot_list = policy.default_reviewer_rotation_list()

        expected_ending_head_of_rotation = rot_list[3]
    
        unassigned_url = urlreverse(ietf.group.views.manage_review_requests, kwargs={ 'acronym': group.acronym, 'group_type': group.type_id, "assignment_status": "unassigned" })

        postdict = {}
        postdict['reviewrequest'] = [r.id for r in requests]
        # assignments that affect the first 3 reviewers in queue
        for i in range(3):
            postdict['r{}-existing_reviewer'.format(requests[i].pk)] = ''
            postdict['r{}-action'.format(requests[i].pk)] = 'assign'
            postdict['r{}-reviewer'.format(requests[i].pk)] = rot_list[i].email_address()
        # and one out of order assignment
        postdict['r{}-existing_reviewer'.format(requests[3].pk)] = ''
        postdict['r{}-action'.format(requests[3].pk)] = 'assign'
        postdict['r{}-reviewer'.format(requests[3].pk)] = rot_list[5].email_address()
        postdict['action'] = 'save'
        self.client.login(username=secretary.person.user.username,password=secretary.person.user.username+'+password')
        r = self.client.post(unassigned_url, postdict)
        self.assertEqual(r.status_code,302)
        self.assertEqual(expected_ending_head_of_rotation, policy.default_reviewer_rotation_list()[0])
        self.assertMailboxContains(outbox, subject='Last Call', text='Requested by', count=4)
     
class ResetNextReviewerInTeamTests(TestCase):

    def test_reviewer_overview_navigation(self):
        group = ReviewTeamFactory(settings__reviewer_queue_policy_id = 'RotateAlphabetically')
        url = urlreverse(ietf.group.views.reviewer_overview, kwargs={ 'acronym': group.acronym })

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertFalse(q('#reset_next_reviewer'))

        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('#reset_next_reviewer'))

        group.reviewteamsettings.reviewer_queue_policy_id='LeastRecentlyUsed'
        group.reviewteamsettings.save()

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertFalse(q('#reset_next_reviewer'))


    def test_reset_next_reviewer(self):
        PersonFactory(user__username='plain')
        for group in (GroupFactory(), ReviewTeamFactory(settings__reviewer_queue_policy_id='LeastRecentlyUsed')):
            url = urlreverse('ietf.group.views.reset_next_reviewer', kwargs=dict(acronym=group.acronym))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302)
            self.client.login(username='plain',password='plain+password')
            r = self.client.get(url)
            self.assertEqual(r.status_code, 404)
            self.client.logout()

        group = ReviewTeamFactory(settings__reviewer_queue_policy_id='RotateAlphabetically')
        secr = RoleFactory(name_id='secr',group=group).person
        reviewers = RoleFactory.create_batch(10, name_id='reviewer',group=group)
        NextReviewerInTeam.objects.create(team = group, next_reviewer=reviewers[4].person)

        target_index = 6
        url = urlreverse('ietf.group.views.reset_next_reviewer', kwargs=dict(acronym=group.acronym))
        for user in (secr.user.username, 'secretary'):
            login_testing_unauthorized(self,user,url)
            r = self.client.get(url)
            self.assertEqual(r.status_code,200)
            r = self.client.post(url,{'next_reviewer':reviewers[target_index].person.pk})
            self.assertEqual(r.status_code,302)
            self.assertEqual(NextReviewerInTeam.objects.get(team=group).next_reviewer, reviewers[target_index].person)
            self.client.logout()
            target_index += 2

class RequestsHistoryTests(TestCase):
    def test_requests_history_overview_page(self):
        # Make assigned assignment
        review_req = ReviewRequestFactory(state_id='assigned')
        assignment = ReviewAssignmentFactory(review_request=review_req,
                                             state_id='assigned',
                                             reviewer=EmailFactory(),
                                             assigned_on = review_req.time)
        group = review_req.team

        for url in [urlreverse(ietf.group.views.review_requests_history,
                               kwargs={ 'acronym': group.acronym }),
                    urlreverse(ietf.group.views.review_requests_history,
                               kwargs={ 'acronym': group.acronym ,
                                        'group_type': group.type_id}),
                    urlreverse(ietf.group.views.review_requests_history,
                               kwargs={ 'acronym': group.acronym }) +
                    '?since=3m',
                    urlreverse(ietf.group.views.review_requests_history,
                               kwargs={ 'acronym': group.acronym ,
                                        'group_type': group.type_id }) +
                    '?since=3m']:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, review_req.doc.name)
            self.assertContains(r, 'Assigned')
            self.assertContains(r, escape(assignment.reviewer.person.name))

        url = urlreverse(ietf.group.views.review_requests_history,
                         kwargs={ 'acronym': group.acronym })

        assignment.state = ReviewAssignmentStateName.objects.get(slug="completed")
        assignment.result = ReviewResultName.objects.get(slug="ready")
        assignment.save()

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, review_req.doc.name)
        self.assertContains(r, 'Assigned')
        self.assertContains(r, 'Completed')

    def test_requests_history_filter_page(self):
        # First assignment as assigned
        review_req = ReviewRequestFactory(state_id = 'assigned',
                                          doc = DocumentFactory())
        assignment = ReviewAssignmentFactory(review_request = review_req,
                                             state_id = 'assigned',
                                             reviewer = EmailFactory(),
                                             assigned_on = review_req.time)
        group = review_req.team

        # Second assignment in same group as accepted
        review_req2 = ReviewRequestFactory(state_id = 'assigned',
                                           team = review_req.team,
                                           doc = DocumentFactory())
        assignment2 = ReviewAssignmentFactory(review_request = review_req2,
                                              state_id='accepted',
                                              reviewer = EmailFactory(),
                                              assigned_on = review_req2.time)

        # Modify the assignment to be completed, and mark it ready
        assignment2.state = ReviewAssignmentStateName.objects.get(slug="completed")
        assignment2.result = ReviewResultName.objects.get(slug="ready")
        assignment2.save()

        # Check that we have all information when we do not filter
        url = urlreverse(ietf.group.views.review_requests_history,
                         kwargs={ 'acronym': group.acronym })
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, review_req.doc.name)
        self.assertContains(r, review_req2.doc.name)
        self.assertContains(r, 'Assigned')
        self.assertContains(r, 'Accepted')
        self.assertContains(r, 'Completed')
        self.assertContains(r, 'Ready')
        self.assertContains(r, escape(assignment.reviewer.person.name))
        self.assertContains(r, escape(assignment2.reviewer.person.name))

        # Check first reviewer history
        for url in [urlreverse(ietf.group.views.review_requests_history,
                               kwargs={ 'acronym': group.acronym }) +
                    '?reviewer_email=' + str(assignment.reviewer),
                    urlreverse(ietf.group.views.review_requests_history,
                               kwargs={ 'acronym': group.acronym ,
                                        'group_type': group.type_id}) +
                    '?reviewer_email=' + str(assignment.reviewer)]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, review_req.doc.name)
            self.assertNotContains(r, review_req2.doc.name)
            self.assertContains(r, 'Assigned')
            self.assertNotContains(r, 'Accepted')
            self.assertNotContains(r, 'Completed')
            self.assertNotContains(r, 'Ready')
            self.assertContains(r, escape(assignment.reviewer.person.name))
            self.assertNotContains(r, escape(assignment2.reviewer.person.name))

        # Check second reviewer history
        for url in [urlreverse(ietf.group.views.review_requests_history,
                               kwargs={ 'acronym': group.acronym }) +
                    '?reviewer_email=' + str(assignment2.reviewer),
                    urlreverse(ietf.group.views.review_requests_history,
                               kwargs={ 'acronym': group.acronym ,
                                        'group_type': group.type_id}) +
                    '?reviewer_email=' + str(assignment2.reviewer)]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, review_req.doc.name)
            self.assertContains(r, review_req2.doc.name)
            self.assertNotContains(r, 'Assigned')
            self.assertContains(r, 'Accepted')
            self.assertContains(r, 'Completed')
            self.assertContains(r, 'Ready')
            self.assertNotContains(r, escape(assignment.reviewer.person.name))
            self.assertContains(r, escape(assignment2.reviewer.person.name))

        # Check for reviewer that does not have anything
        url = urlreverse(ietf.group.views.review_requests_history,
                         kwargs={ 'acronym': group.acronym }) + '?reviewer_email=nobody@nowhere.example.org'

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, review_req.doc.name)
        self.assertNotContains(r, 'Assigned')
        self.assertNotContains(r, 'Accepted')
        self.assertNotContains(r, 'Completed')

    def test_requests_history_invalid_filter_parameters(self):
        # First assignment as assigned
        review_req = ReviewRequestFactory(state_id="assigned", doc=DocumentFactory())
        group = review_req.team
        url = urlreverse(
            "ietf.group.views.review_requests_history",
            kwargs={"acronym": group.acronym},
        )
        invalid_reviewer_emails = [
            "%00null@example.com",  # urlencoded null character
            "null@exa%00mple.com",  # urlencoded null character
            "\x00null@example.com",  # literal null character
            "null@ex\x00ample.com",  # literal null character
        ]
        for invalid_email in invalid_reviewer_emails:
            r = self.client.get(
                url + f"?reviewer_email={invalid_email}"
            )
            self.assertEqual(
                r.status_code, 
                400,
                f"should return a 400 response for reviewer_email={repr(invalid_email)}"
            )

        invalid_since_choices = [
            "forever",  # not an option
            "all\x00",  # literal null character
            "a%00ll",  # urlencoded null character
        ]
        for invalid_since in invalid_since_choices:
            r = self.client.get(
                url + f"?since={invalid_since}"
            )
            self.assertEqual(
                r.status_code, 
                400,
                f"should return a 400 response for since={repr(invalid_since)}"
            )
