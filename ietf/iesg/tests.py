# Copyright The IETF Trust 2009-2021, All Rights Reserved
# -*- coding: utf-8 -*-


from collections import Counter
import datetime
import io
import tarfile

from pathlib import Path
from pyquery import PyQuery

from django.conf import settings
from django.urls import reverse as urlreverse
from django.utils.encoding import force_bytes
from django.utils.html import escape

import debug                            # pyflakes:ignore

from ietf.doc.models import DocEvent, BallotPositionDocEvent, TelechatDocEvent
from ietf.doc.models import Document, State, RelatedDocument
from ietf.doc.factories import BallotDocEventFactory, BallotPositionDocEventFactory, TelechatDocEventFactory, WgDraftFactory, IndividualDraftFactory, ConflictReviewFactory, BaseDocumentFactory, CharterFactory, WgRfcFactory, IndividualRfcFactory
from ietf.doc.utils import create_ballot_if_not_open
from ietf.group.factories import RoleFactory, GroupFactory, DatedGroupMilestoneFactory, DatelessGroupMilestoneFactory
from ietf.group.models import Group, GroupMilestone, Role
from ietf.iesg.agenda import get_agenda_date, agenda_data, fill_in_agenda_administrivia, agenda_sections
from ietf.iesg.models import TelechatDate, TelechatAgendaContent
from ietf.iesg.utils import get_wg_dashboard_info
from ietf.name.models import StreamName, TelechatAgendaSectionName
from ietf.person.factories import PersonFactory
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent
from ietf.iesg.factories import IESGMgmtItemFactory, TelechatAgendaContentFactory
from ietf.utils.timezone import date_today, DEADLINE_TZINFO

class IESGTests(TestCase):
    def test_feed(self):
        draft = WgDraftFactory(states=[('draft','active'),('draft-iesg','iesg-eva')],ad=Person.objects.get(user__username='ad'))

        ad = Person.objects.get(user__username="ad")
        ballot = create_ballot_if_not_open(None, draft, ad, 'approve')
        pos = BallotPositionDocEvent()
        pos.ballot = ballot
        pos.pos_id = "discuss"
        pos.type = "changed_ballot_position"
        pos.doc = draft
        pos.rev = draft.rev
        pos.balloter = pos.by = Person.objects.get(user__username="ad")
        pos.save()

        r = self.client.get(urlreverse("ietf.iesg.views.discusses"))
        self.assertEqual(r.status_code, 200)

        self.assertContains(r, draft.name)
        self.assertContains(r, escape(pos.balloter.plain_name()))

        # Mark draft as replaced
        draft.set_state(State.objects.get(type="draft", slug="repl"))

        r = self.client.get(urlreverse("ietf.iesg.views.discusses"))
        self.assertEqual(r.status_code, 200)

        self.assertNotContains(r, draft.name)
        self.assertNotContains(r, escape(pos.balloter.plain_name()))

    def test_milestones_needing_review(self):
        draft = WgDraftFactory()
        RoleFactory(name_id='ad',group=draft.group,person=Person.objects.get(user__username='ad'))

        m = GroupMilestone.objects.create(group=draft.group,
                                          state_id="review",
                                          desc="Test milestone",
                                          due=date_today(DEADLINE_TZINFO))

        url = urlreverse("ietf.iesg.views.milestones_needing_review")
        login_testing_unauthorized(self, "ad", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, m.desc)
        draft.group.state_id = 'conclude'
        draft.group.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, m.desc)

    def test_milestones_needing_review_ordering(self):
        dated_group = GroupFactory(uses_milestone_dates=True)
        RoleFactory(
            name_id='ad',
            group=dated_group,
            person=Person.objects.get(user__username='ad'),
        )
        dated_milestones = [
            DatedGroupMilestoneFactory(
                group=dated_group,
                state_id="review",
                desc="This is the description of one dated group milestone",
            ),
            DatedGroupMilestoneFactory(
                group=dated_group,
                state_id="review",
                desc="This is the description of another dated group milestone",
            ),
        ]
        dated_milestones[0].due -= datetime.timedelta(days=1)  # make this one earlier
        dated_milestones[0].save()

        dateless_group = GroupFactory(uses_milestone_dates=False)
        RoleFactory(
            name_id='ad',
            group=dateless_group,
            person=Person.objects.get(user__username='ad'),
        )
        dateless_milestones = [
            DatelessGroupMilestoneFactory(
                group=dateless_group,
                state_id="review",
                desc="This is the description of one dateless group milestone",
            ),
            DatelessGroupMilestoneFactory(
                group=dateless_group,
                state_id="review",
                desc="This is the description of another dateless group milestone",
            ),
        ]

        url = urlreverse("ietf.iesg.views.milestones_needing_review")
        self.client.login(username="ad", password="ad+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        pq = PyQuery(r.content)
        
        # check order-by-date
        dated_tbody = pq(f'td:contains("{dated_milestones[0].desc}")').closest("tbody")
        rows = list(dated_tbody.items("tr"))  # keep as pyquery objects
        self.assertTrue(rows[0].find('td:first:contains("Last")'))  # Last milestone shown first
        self.assertFalse(rows[0].find('td:first:contains("Next")'))
        self.assertTrue(rows[0].find(f'td:contains("{dated_milestones[1].desc}")'))
        self.assertFalse(rows[0].find(f'td:contains("{dated_milestones[0].desc}")'))

        self.assertFalse(rows[1].find('td:first:contains("Last")'))  # Last milestone shown first
        self.assertTrue(rows[1].find('td:first:contains("Next")'))
        self.assertFalse(rows[1].find(f'td:contains("{dated_milestones[1].desc}")'))
        self.assertTrue(rows[1].find(f'td:contains("{dated_milestones[0].desc}")'))

        # check order-by-order
        dateless_tbody = pq(f'td:contains("{dateless_milestones[0].desc}")').closest("tbody")
        rows = list(dateless_tbody.items("tr"))  # keep as pyquery objects
        self.assertTrue(rows[0].find('td:first:contains("Last")'))  # Last milestone shown first
        self.assertFalse(rows[0].find('td:first:contains("Next")'))
        self.assertTrue(rows[0].find(f'td:contains("{dateless_milestones[1].desc}")'))
        self.assertFalse(rows[0].find(f'td:contains("{dateless_milestones[0].desc}")'))

        self.assertFalse(rows[1].find('td:first:contains("Last")'))  # Last milestone shown first
        self.assertTrue(rows[1].find('td:first:contains("Next")'))
        self.assertFalse(rows[1].find(f'td:contains("{dateless_milestones[1].desc}")'))
        self.assertTrue(rows[1].find(f'td:contains("{dateless_milestones[0].desc}")'))


    def test_review_decisions(self):
        draft = WgDraftFactory()

        e = DocEvent(type="iesg_approved")
        e.doc = draft
        e.rev = draft.rev
        e.by = Person.objects.get(name="Areað Irector")
        e.save()

        url = urlreverse('ietf.iesg.views.review_decisions')

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.name)

    def test_photos(self):
        url = urlreverse("ietf.iesg.views.photos")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        ads = Role.objects.filter(group__type='area', group__state='active', name_id='ad')
        self.assertEqual(len(q('.photo')), ads.count())
        
    def test_ietf_activity(self):
        url = urlreverse("ietf.iesg.views.ietf_activity")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_working_groups(self):
        # Clean away the wasted built-for-every-test noise
        Group.objects.filter(type__in=["wg", "area"]).delete()

        (
            area_summary,
            area_totals,
            ad_summary,
            noad_summary,
            ad_totals,
            noad_totals,
            totals,
            wg_summary,
        ) = get_wg_dashboard_info()
        self.assertEqual(area_summary, [])
        self.assertEqual(
            area_totals, {"group_count": 0, "doc_count": 0, "page_count": 0}
        )
        self.assertEqual(ad_summary, [])
        self.assertEqual(noad_summary, [])
        self.assertEqual(
            ad_totals,
            {
                "ad_group_count": 0,
                "doc_group_count": 0,
                "doc_count": 0,
                "page_count": 0,
            },
        )
        self.assertEqual(
            noad_totals,
            {
                "ad_group_count": 0,
                "doc_group_count": 0,
                "doc_count": 0,
                "page_count": 0,
            },
        )
        self.assertEqual(
            totals,
            {
                "group_count": 0,
                "doc_count": 0,
                "page_count": 0,
                "groups_with_docs_count": 0,
            },
        )
        self.assertEqual(wg_summary, [])

        # Construct Areas with WGs similar in shape to a real moment of the IETF

        # Note that this test construciton uses the first letter of the wg acronyms
        # for convenience to switch on whether groups have documents with assigned ADs.
        # (Search for ` if wg_acronym[0] > "g"`)
        # There's no other significance to the names of the area directors or the
        # acronyms of the areas and groups other than being distinct. Taking the
        # values from sets of similar things hopefully helps with debugging the tests.

        areas = {}
        for area_acronym in ["red", "orange", "yellow", "green", "blue", "violet"]:
            areas[area_acronym] = GroupFactory(type_id="area", acronym=area_acronym)
        for ad, area, wgs in [
            ("Alpha", "red", ["bassoon"]),
            ("Bravo", "orange", ["celesta"]),
            ("Charlie", "orange", ["clarinet", "cymbals"]),
            ("Delta", "yellow", ["flute"]),
            ("Echo", "yellow", ["glockenspiel"]),
            ("Foxtrot", "green", ["gong", "guitar"]),
            ("Golf", "green", ["harp"]),
            ("Hotel", "blue", ["harpsichord"]),
            ("Indigo", "blue", ["oboe", "organ"]),
            ("Juliet", "violet", ["piano"]),
            ("Kilo", "violet", ["piccolo"]),
            ("Lima", "violet", ["saxophone", "tambourine"]),
        ]:
            p = Person.objects.filter(name=ad).first() or PersonFactory(name=ad)
            RoleFactory(group=areas[area], person=p, name_id="ad")
            for wg in wgs:
                g = GroupFactory(acronym=wg, type_id="wg", parent=areas[area])
                RoleFactory(group=g, person=p, name_id="ad")

        # Some ADs have out of area groups
        g = GroupFactory(acronym="timpani", parent=areas["orange"])
        RoleFactory(group=g, person=Person.objects.get(name="Juliet"), name_id="ad")

        (
            area_summary,
            area_totals,
            ad_summary,
            noad_summary,
            ad_totals,
            noad_totals,
            totals,
            wg_summary,
        ) = get_wg_dashboard_info()

        # checks for the expected result with area sorted by name
        self.assertEqual(
            area_summary,
            [
                {
                    "area": "blue",
                    "groups_in_area": 3,
                    "groups_with_docs": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "area": "green",
                    "groups_in_area": 3,
                    "groups_with_docs": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "area": "orange",
                    "groups_in_area": 4,
                    "groups_with_docs": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "area": "red",
                    "groups_in_area": 1,
                    "groups_with_docs": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "area": "violet",
                    "groups_in_area": 4,
                    "groups_with_docs": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "area": "yellow",
                    "groups_in_area": 2,
                    "groups_with_docs": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
            ],
        )
        self.assertEqual(
            area_totals, {"group_count": 0, "doc_count": 0, "page_count": 0}
        )
        self.assertEqual(
            ad_summary,
            [
                {
                    "ad": "Alpha",
                    "area": "red",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Bravo",
                    "area": "orange",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Charlie",
                    "area": "orange",
                    "ad_group_count": 2,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Delta",
                    "area": "yellow",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Echo",
                    "area": "yellow",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Foxtrot",
                    "area": "green",
                    "ad_group_count": 2,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Golf",
                    "area": "green",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Hotel",
                    "area": "blue",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Indigo",
                    "area": "blue",
                    "ad_group_count": 2,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Juliet",
                    "area": "orange",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Juliet",
                    "area": "violet",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Kilo",
                    "area": "violet",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Lima",
                    "area": "violet",
                    "ad_group_count": 2,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
            ],
        )
        self.assertEqual(
            noad_summary,
            [
                {
                    "ad": "Alpha",
                    "area": "red",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Bravo",
                    "area": "orange",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Charlie",
                    "area": "orange",
                    "ad_group_count": 2,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Delta",
                    "area": "yellow",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Echo",
                    "area": "yellow",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Foxtrot",
                    "area": "green",
                    "ad_group_count": 2,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Golf",
                    "area": "green",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Hotel",
                    "area": "blue",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Indigo",
                    "area": "blue",
                    "ad_group_count": 2,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Juliet",
                    "area": "orange",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Juliet",
                    "area": "violet",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Kilo",
                    "area": "violet",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
                {
                    "ad": "Lima",
                    "area": "violet",
                    "ad_group_count": 2,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0,
                    "doc_percent": 0,
                    "page_percent": 0,
                },
            ],
        )
        self.assertEqual(
            ad_totals,
            {
                "ad_group_count": 17,
                "doc_group_count": 0,
                "doc_count": 0,
                "page_count": 0,
            },
        )
        self.assertEqual(
            noad_totals,
            {
                "ad_group_count": 17,
                "doc_group_count": 0,
                "doc_count": 0,
                "page_count": 0,
            },
        )
        self.assertEqual(
            totals,
            {
                "group_count": 17,
                "doc_count": 0,
                "page_count": 0,
                "groups_with_docs_count": 0,
            },
        )
        self.assertEqual(
            wg_summary,
            [
                {
                    "wg": "bassoon",
                    "area": "red",
                    "ad": "Alpha",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "celesta",
                    "area": "orange",
                    "ad": "Bravo",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "clarinet",
                    "area": "orange",
                    "ad": "Charlie",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "cymbals",
                    "area": "orange",
                    "ad": "Charlie",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "flute",
                    "area": "yellow",
                    "ad": "Delta",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "glockenspiel",
                    "area": "yellow",
                    "ad": "Echo",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "gong",
                    "area": "green",
                    "ad": "Foxtrot",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "guitar",
                    "area": "green",
                    "ad": "Foxtrot",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "harp",
                    "area": "green",
                    "ad": "Golf",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "harpsichord",
                    "area": "blue",
                    "ad": "Hotel",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "oboe",
                    "area": "blue",
                    "ad": "Indigo",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "organ",
                    "area": "blue",
                    "ad": "Indigo",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "piano",
                    "area": "violet",
                    "ad": "Juliet",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "piccolo",
                    "area": "violet",
                    "ad": "Kilo",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "saxophone",
                    "area": "violet",
                    "ad": "Lima",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "tambourine",
                    "area": "violet",
                    "ad": "Lima",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "timpani",
                    "area": "orange",
                    "ad": "Juliet",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
            ],
        )

        # As seen above, all doc and page counts are currently 0

        # We'll give a group a document but not assign it to its AD
        WgDraftFactory(
            group=Group.objects.get(acronym="saxophone"), pages=len("saxophone")
        )
        (
            area_summary,
            area_totals,
            ad_summary,
            noad_summary,
            ad_totals,
            noad_totals,
            totals,
            wg_summary,
        ) = get_wg_dashboard_info()
        count_violet_dicts = 0
        for d in area_summary:
            if d["area"] == "violet":
                count_violet_dicts += 1
                self.assertEqual(d["groups_with_docs"], 1)
                self.assertEqual(d["doc_count"], 1)
                self.assertEqual(d["page_count"], 9)
                self.assertEqual(d["group_percent"], 100.0)
                self.assertEqual(d["doc_percent"], 100.0)
                self.assertEqual(d["page_percent"], 100.0)
            else:
                self.assertEqual(d["groups_with_docs"], 0)
                self.assertEqual(d["doc_count"], 0)
                self.assertEqual(d["page_count"], 0)
                self.assertEqual(d["group_percent"], 0)
                self.assertEqual(d["doc_percent"], 0)
                self.assertEqual(d["page_percent"], 0)
        self.assertEqual(count_violet_dicts, 1)

        self.assertEqual(
            area_totals, {"group_count": 1, "doc_count": 1, "page_count": 9}
        )

        # No AD has this document, even though it's in Lima's group
        count_lima_dicts = 0
        for d in ad_summary:
            if d["ad"] == "Lima":
                count_lima_dicts += 1
            self.assertEqual(d["doc_group_count"], 0)
            self.assertEqual(d["doc_count"], 0)
            self.assertEqual(d["page_count"], 0)
            self.assertEqual(d["group_percent"], 0)
            self.assertEqual(d["doc_percent"], 0)
            self.assertEqual(d["page_percent"], 0)
        self.assertEqual(count_lima_dicts, 1)

        # It's in Lima's group, so normally it will eventually land on Lima
        count_lima_dicts = 0
        for d in noad_summary:
            if d["ad"] == "Lima":
                count_lima_dicts += 1
                self.assertEqual(d["doc_group_count"], 1)
                self.assertEqual(d["doc_count"], 1)
                self.assertEqual(d["page_count"], 9)
                self.assertEqual(d["group_percent"], 100.0)
                self.assertEqual(d["doc_percent"], 100.0)
                self.assertEqual(d["page_percent"], 100.0)
            else:
                self.assertEqual(d["doc_group_count"], 0)
                self.assertEqual(d["doc_count"], 0)
                self.assertEqual(d["page_count"], 0)
                self.assertEqual(d["group_percent"], 0)
                self.assertEqual(d["doc_percent"], 0)
                self.assertEqual(d["page_percent"], 0)
        self.assertEqual(count_lima_dicts, 1)

        self.assertEqual(
            ad_totals,
            {
                "ad_group_count": 17,
                "doc_group_count": 0,
                "doc_count": 0,
                "page_count": 0,
            },
        )
        self.assertEqual(
            noad_totals,
            {
                "ad_group_count": 17,
                "doc_group_count": 1,
                "doc_count": 1,
                "page_count": 9,
            },
        )
        self.assertEqual(
            totals,
            {
                "group_count": 17,
                "doc_count": 1,
                "page_count": 9,
                "groups_with_docs_count": 1,
            },
        )

        count_sax_dicts = 0
        for d in wg_summary:
            if d["wg"] == "saxophone":
                count_sax_dicts += 1
                self.assertEqual(d["doc_count"], 1)
                self.assertEqual(d["page_count"], 9)
            else:
                self.assertEqual(d["doc_count"], 0)
                self.assertEqual(d["page_count"], 0)
        self.assertEqual(count_sax_dicts, 1)

        # Assign that doc to Lima
        self.assertEqual(Document.objects.count(), 1)
        Document.objects.all().update(ad=Person.objects.get(name="Lima"))
        (
            area_summary,
            area_totals,
            ad_summary,
            noad_summary,
            ad_totals,
            noad_totals,
            totals,
            wg_summary,
        ) = get_wg_dashboard_info()
        count_violet_dicts = 0
        for d in area_summary:
            if d["area"] == "violet":
                count_violet_dicts += 1
                self.assertEqual(d["groups_with_docs"], 1)
                self.assertEqual(d["doc_count"], 1)
                self.assertEqual(d["page_count"], 9)
                self.assertEqual(d["group_percent"], 100.0)
                self.assertEqual(d["doc_percent"], 100.0)
                self.assertEqual(d["page_percent"], 100.0)
            else:
                self.assertEqual(d["groups_with_docs"], 0)
                self.assertEqual(d["doc_count"], 0)
                self.assertEqual(d["page_count"], 0)
                self.assertEqual(d["group_percent"], 0)
                self.assertEqual(d["doc_percent"], 0)
                self.assertEqual(d["page_percent"], 0)
        self.assertEqual(count_violet_dicts, 1)

        self.assertEqual(
            area_totals, {"group_count": 1, "doc_count": 1, "page_count": 9}
        )

        # This time it will show up as a doc assigned to Lima
        count_lima_dicts = 0
        for d in ad_summary:
            if d["ad"] == "Lima":
                count_lima_dicts += 1
                self.assertEqual(d["doc_group_count"], 1)
                self.assertEqual(d["doc_count"], 1)
                self.assertEqual(d["page_count"], 9)
                self.assertEqual(d["group_percent"], 100.0)
                self.assertEqual(d["doc_percent"], 100.0)
                self.assertEqual(d["page_percent"], 100.0)
            else:
                self.assertEqual(d["doc_group_count"], 0)
                self.assertEqual(d["doc_count"], 0)
                self.assertEqual(d["page_count"], 0)
                self.assertEqual(d["group_percent"], 0)
                self.assertEqual(d["doc_percent"], 0)
                self.assertEqual(d["page_percent"], 0)
        self.assertEqual(count_lima_dicts, 1)

        # and there will be no noad documents
        count_lima_dicts = 0
        for d in noad_summary:
            if d["ad"] == "Lima":
                count_lima_dicts += 1
            self.assertEqual(d["doc_group_count"], 0)
            self.assertEqual(d["doc_count"], 0)
            self.assertEqual(d["page_count"], 0)
            self.assertEqual(d["group_percent"], 0)
            self.assertEqual(d["doc_percent"], 0)
            self.assertEqual(d["page_percent"], 0)
        self.assertEqual(count_lima_dicts, 1)

        self.assertEqual(
            ad_totals,
            {
                "ad_group_count": 17,
                "doc_group_count": 1,
                "doc_count": 1,
                "page_count": 9,
            },
        )
        self.assertEqual(
            noad_totals,
            {
                "ad_group_count": 17,
                "doc_group_count": 0,
                "doc_count": 0,
                "page_count": 0,
            },
        )
        self.assertEqual(
            totals,
            {
                "group_count": 17,
                "doc_count": 1,
                "page_count": 9,
                "groups_with_docs_count": 1,
            },
        )

        count_sax_dicts = 0
        for d in wg_summary:
            if d["wg"] == "saxophone":
                count_sax_dicts += 1
                self.assertEqual(d["doc_count"], 1)
                self.assertEqual(d["page_count"], 9)
            else:
                self.assertEqual(d["doc_count"], 0)
                self.assertEqual(d["page_count"], 0)
        self.assertEqual(count_sax_dicts, 1)

        # Now give Lima a document in a group that's not in their area:
        WgDraftFactory(
            group=Group.objects.get(acronym="gong"),
            pages=len("gong"),
            ad=Person.objects.get(name="Lima"),
        )
        (
            area_summary,
            area_totals,
            ad_summary,
            noad_summary,
            ad_totals,
            noad_totals,
            totals,
            wg_summary,
        ) = get_wg_dashboard_info()
        seen_dicts = Counter([d["area"] for d in area_summary])
        for d in areas:
            self.assertEqual(seen_dicts[area], 1 if area in ["violet", "green"] else 0)
        for d in area_summary:
            if d["area"] in ["violet", "green"]:
                self.assertEqual(d["doc_count"], 1)
                self.assertEqual(d["page_count"], 9 if d["area"] == "violet" else 4)
                self.assertEqual(d["group_percent"], 50)
                self.assertEqual(d["doc_percent"], 50)
                self.assertEqual(
                    d["page_percent"],
                    100 * 9 / 13 if d["area"] == "violet" else 100 * 4 / 13,
                )
            else:
                self.assertEqual(d["doc_count"], 0)
                self.assertEqual(d["page_count"], 0)
                self.assertEqual(d["group_percent"], 0)
                self.assertEqual(d["doc_percent"], 0)
                self.assertEqual(d["page_percent"], 0)

        self.assertEqual(
            area_totals, {"group_count": 2, "doc_count": 2, "page_count": 13}
        )

        for d in ad_summary:
            if d["ad"] == "Lima":
                self.assertEqual(d["doc_group_count"], 1)
                self.assertEqual(d["doc_count"], 1)
                self.assertEqual(d["page_count"], 9 if d["area"] == "violet" else 4)
                self.assertEqual(d["group_percent"], 50)
                self.assertEqual(d["doc_percent"], 50)
                self.assertEqual(
                    d["page_percent"],
                    100 * 9 / 13 if d["area"] == "violet" else 100 * 4 / 13,
                )
            else:
                self.assertEqual(d["doc_group_count"], 0)
                self.assertEqual(
                    d["doc_count"], 0
                )  # Note in particular this is 0 for Foxtrot
                self.assertEqual(d["page_count"], 0)
                self.assertEqual(d["group_percent"], 0)
                self.assertEqual(d["doc_percent"], 0)
                self.assertEqual(d["page_percent"], 0)

        for d in wg_summary:
            if d["wg"] == "gong":
                # Lima's doc in gong above counts at the dict for gong even though the ad reported there is Foxtrot.
                self.assertEqual(
                    d,
                    {
                        "wg": "gong",
                        "area": "green",
                        "ad": "Foxtrot",
                        "doc_count": 1,
                        "page_count": 4,
                        "rfc_count": 0,
                        "recent_rfc_count": 0,
                    },
                )
            elif d["ad"] == "Lima":
                self.assertEqual(
                    d["area"], "violet"
                )  # The out of area assignment is not reflected in the wg_summary at all.

        # Now pile on a lot of documents
        for wg_acronym in [
            "bassoon",
            "celesta",
            "clarinet",
            "cymbals",
            "flute",
            "glockenspiel",
            "gong",
            "guitar",
            "harp",
            "harpsichord",
            "oboe",
            "organ",
            "piano",
            "piccolo",
            "saxophone",
            "tambourine",
            "timpani",
        ]:
            if wg_acronym in ["bassoon", "celesta"]:
                continue  # Those WGs have no docs
            # The rest have a doc that's not assigned to any ad
            WgDraftFactory(
                group=Group.objects.get(acronym=wg_acronym), pages=len(wg_acronym)
            )
            if wg_acronym[0] > "g":
                # Some have a doc assigned to the responsible ad
                WgDraftFactory(
                    group=Group.objects.get(acronym=wg_acronym),
                    pages=len(wg_acronym),
                    ad=Role.objects.get(name_id="ad", group__acronym=wg_acronym).person,
                )
        # The other AD for an area might be covering a doc
        WgDraftFactory(
            group=Group.objects.get(acronym="saxophone"),
            pages=len("saxophone"),
            ad=Person.objects.get(name="Juliet"),
        )
        # An Ad not associated with the group or the area is responsible for a doc
        WgDraftFactory(
            group=Group.objects.get(acronym="bassoon"),
            pages=len("bassoon"),
            ad=Person.objects.get(name="Juliet"),
        )

        (
            area_summary,
            area_totals,
            ad_summary,
            noad_summary,
            ad_totals,
            noad_totals,
            totals,
            wg_summary,
        ) = get_wg_dashboard_info()

        self.assertEqual(
            area_summary,
            [
                {
                    "area": "blue",
                    "groups_in_area": 3,
                    "groups_with_docs": 3,
                    "doc_count": 6,
                    "page_count": 40,
                    "group_percent": 18.75,
                    "doc_percent": 21.428571428571427,
                    "page_percent": 20.51282051282051,
                },
                {
                    "area": "green",
                    "groups_in_area": 3,
                    "groups_with_docs": 3,
                    "doc_count": 5,
                    "page_count": 22,
                    "group_percent": 18.75,
                    "doc_percent": 17.857142857142858,
                    "page_percent": 11.282051282051283,
                },
                {
                    "area": "orange",
                    "groups_in_area": 4,
                    "groups_with_docs": 3,
                    "doc_count": 4,
                    "page_count": 29,
                    "group_percent": 18.75,
                    "doc_percent": 14.285714285714285,
                    "page_percent": 14.871794871794872,
                },
                {
                    "area": "red",
                    "groups_in_area": 1,
                    "groups_with_docs": 1,
                    "doc_count": 1,
                    "page_count": 7,
                    "group_percent": 6.25,
                    "doc_percent": 3.571428571428571,
                    "page_percent": 3.5897435897435894,
                },
                {
                    "area": "violet",
                    "groups_in_area": 4,
                    "groups_with_docs": 4,
                    "doc_count": 10,
                    "page_count": 80,
                    "group_percent": 25.0,
                    "doc_percent": 35.714285714285715,
                    "page_percent": 41.02564102564102,
                },
                {
                    "area": "yellow",
                    "groups_in_area": 2,
                    "groups_with_docs": 2,
                    "doc_count": 2,
                    "page_count": 17,
                    "group_percent": 12.5,
                    "doc_percent": 7.142857142857142,
                    "page_percent": 8.717948717948717,
                },
            ],
        )
        self.assertEqual(
            area_totals, {"group_count": 16, "doc_count": 28, "page_count": 195}
        )
        self.assertEqual(
            ad_summary,
            [
                {
                    "ad": "Alpha",
                    "area": "red",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0.0,
                    "doc_percent": 0.0,
                    "page_percent": 0.0,
                },
                {
                    "ad": "Bravo",
                    "area": "orange",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0.0,
                    "doc_percent": 0.0,
                    "page_percent": 0.0,
                },
                {
                    "ad": "Charlie",
                    "area": "orange",
                    "ad_group_count": 2,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0.0,
                    "doc_percent": 0.0,
                    "page_percent": 0.0,
                },
                {
                    "ad": "Delta",
                    "area": "yellow",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0.0,
                    "doc_percent": 0.0,
                    "page_percent": 0.0,
                },
                {
                    "ad": "Echo",
                    "area": "yellow",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0.0,
                    "doc_percent": 0.0,
                    "page_percent": 0.0,
                },
                {
                    "ad": "Foxtrot",
                    "area": "green",
                    "ad_group_count": 2,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0.0,
                    "doc_percent": 0.0,
                    "page_percent": 0.0,
                },
                {
                    "ad": "Golf",
                    "area": "green",
                    "ad_group_count": 1,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 4,
                    "group_percent": 8.333333333333332,
                    "doc_percent": 7.6923076923076925,
                    "page_percent": 4.395604395604396,
                },
                {
                    "ad": "Hotel",
                    "area": "blue",
                    "ad_group_count": 1,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 11,
                    "group_percent": 8.333333333333332,
                    "doc_percent": 7.6923076923076925,
                    "page_percent": 12.087912087912088,
                },
                {
                    "ad": "Indigo",
                    "area": "blue",
                    "ad_group_count": 2,
                    "doc_group_count": 2,
                    "doc_count": 2,
                    "page_count": 9,
                    "group_percent": 16.666666666666664,
                    "doc_percent": 15.384615384615385,
                    "page_percent": 9.89010989010989,
                },
                {
                    "ad": "Juliet",
                    "area": "orange",
                    "ad_group_count": 1,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 7,
                    "group_percent": 8.333333333333332,
                    "doc_percent": 7.6923076923076925,
                    "page_percent": 7.6923076923076925,
                },
                {
                    "ad": "Juliet",
                    "area": "red",
                    "ad_group_count": 0,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 7,
                    "group_percent": 8.333333333333332,
                    "doc_percent": 7.6923076923076925,
                    "page_percent": 7.6923076923076925,
                },
                {
                    "ad": "Juliet",
                    "area": "violet",
                    "ad_group_count": 1,
                    "doc_group_count": 2,
                    "doc_count": 2,
                    "page_count": 14,
                    "group_percent": 16.666666666666664,
                    "doc_percent": 15.384615384615385,
                    "page_percent": 15.384615384615385,
                },
                {
                    "ad": "Kilo",
                    "area": "violet",
                    "ad_group_count": 1,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 7,
                    "group_percent": 8.333333333333332,
                    "doc_percent": 7.6923076923076925,
                    "page_percent": 7.6923076923076925,
                },
                {
                    "ad": "Lima",
                    "area": "green",
                    "ad_group_count": 0,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 4,
                    "group_percent": 8.333333333333332,
                    "doc_percent": 7.6923076923076925,
                    "page_percent": 4.395604395604396,
                },
                {
                    "ad": "Lima",
                    "area": "violet",
                    "ad_group_count": 2,
                    "doc_group_count": 2,
                    "doc_count": 3,
                    "page_count": 28,
                    "group_percent": 16.666666666666664,
                    "doc_percent": 23.076923076923077,
                    "page_percent": 30.76923076923077,
                },
            ],
        )
        self.assertEqual(
            noad_summary,
            [
                {
                    "ad": "Alpha",
                    "area": "red",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0.0,
                    "doc_percent": 0.0,
                    "page_percent": 0.0,
                },
                {
                    "ad": "Bravo",
                    "area": "orange",
                    "ad_group_count": 1,
                    "doc_group_count": 0,
                    "doc_count": 0,
                    "page_count": 0,
                    "group_percent": 0.0,
                    "doc_percent": 0.0,
                    "page_percent": 0.0,
                },
                {
                    "ad": "Charlie",
                    "area": "orange",
                    "ad_group_count": 2,
                    "doc_group_count": 2,
                    "doc_count": 2,
                    "page_count": 15,
                    "group_percent": 13.333333333333334,
                    "doc_percent": 13.333333333333334,
                    "page_percent": 14.423076923076922,
                },
                {
                    "ad": "Delta",
                    "area": "yellow",
                    "ad_group_count": 1,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 5,
                    "group_percent": 6.666666666666667,
                    "doc_percent": 6.666666666666667,
                    "page_percent": 4.807692307692308,
                },
                {
                    "ad": "Echo",
                    "area": "yellow",
                    "ad_group_count": 1,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 12,
                    "group_percent": 6.666666666666667,
                    "doc_percent": 6.666666666666667,
                    "page_percent": 11.538461538461538,
                },
                {
                    "ad": "Foxtrot",
                    "area": "green",
                    "ad_group_count": 2,
                    "doc_group_count": 2,
                    "doc_count": 2,
                    "page_count": 10,
                    "group_percent": 13.333333333333334,
                    "doc_percent": 13.333333333333334,
                    "page_percent": 9.615384615384617,
                },
                {
                    "ad": "Golf",
                    "area": "green",
                    "ad_group_count": 1,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 4,
                    "group_percent": 6.666666666666667,
                    "doc_percent": 6.666666666666667,
                    "page_percent": 3.8461538461538463,
                },
                {
                    "ad": "Hotel",
                    "area": "blue",
                    "ad_group_count": 1,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 11,
                    "group_percent": 6.666666666666667,
                    "doc_percent": 6.666666666666667,
                    "page_percent": 10.576923076923077,
                },
                {
                    "ad": "Indigo",
                    "area": "blue",
                    "ad_group_count": 2,
                    "doc_group_count": 2,
                    "doc_count": 2,
                    "page_count": 9,
                    "group_percent": 13.333333333333334,
                    "doc_percent": 13.333333333333334,
                    "page_percent": 8.653846153846153,
                },
                {
                    "ad": "Juliet",
                    "area": "orange",
                    "ad_group_count": 1,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 7,
                    "group_percent": 6.666666666666667,
                    "doc_percent": 6.666666666666667,
                    "page_percent": 6.730769230769231,
                },
                {
                    "ad": "Juliet",
                    "area": "violet",
                    "ad_group_count": 1,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 5,
                    "group_percent": 6.666666666666667,
                    "doc_percent": 6.666666666666667,
                    "page_percent": 4.807692307692308,
                },
                {
                    "ad": "Kilo",
                    "area": "violet",
                    "ad_group_count": 1,
                    "doc_group_count": 1,
                    "doc_count": 1,
                    "page_count": 7,
                    "group_percent": 6.666666666666667,
                    "doc_percent": 6.666666666666667,
                    "page_percent": 6.730769230769231,
                },
                {
                    "ad": "Lima",
                    "area": "violet",
                    "ad_group_count": 2,
                    "doc_group_count": 2,
                    "doc_count": 2,
                    "page_count": 19,
                    "group_percent": 13.333333333333334,
                    "doc_percent": 13.333333333333334,
                    "page_percent": 18.269230769230766,
                },
            ],
        )
        self.assertEqual(
            ad_totals,
            {
                "ad_group_count": 17,
                "doc_group_count": 12,
                "doc_count": 13,
                "page_count": 91,
            },
        )
        self.assertEqual(
            noad_totals,
            {
                "ad_group_count": 17,
                "doc_group_count": 15,
                "doc_count": 15,
                "page_count": 104,
            },
        )
        self.assertEqual(
            totals,
            {
                "group_count": 17,
                "doc_count": 28,
                "page_count": 195,
                "groups_with_docs_count": 16,
            },
        )
        self.assertEqual(
            wg_summary,
            [
                {
                    "wg": "bassoon",
                    "area": "red",
                    "ad": "Alpha",
                    "doc_count": 1,
                    "page_count": 7,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "celesta",
                    "area": "orange",
                    "ad": "Bravo",
                    "doc_count": 0,
                    "page_count": 0,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "clarinet",
                    "area": "orange",
                    "ad": "Charlie",
                    "doc_count": 1,
                    "page_count": 8,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "cymbals",
                    "area": "orange",
                    "ad": "Charlie",
                    "doc_count": 1,
                    "page_count": 7,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "flute",
                    "area": "yellow",
                    "ad": "Delta",
                    "doc_count": 1,
                    "page_count": 5,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "glockenspiel",
                    "area": "yellow",
                    "ad": "Echo",
                    "doc_count": 1,
                    "page_count": 12,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "gong",
                    "area": "green",
                    "ad": "Foxtrot",
                    "doc_count": 2,
                    "page_count": 8,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "guitar",
                    "area": "green",
                    "ad": "Foxtrot",
                    "doc_count": 1,
                    "page_count": 6,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "harp",
                    "area": "green",
                    "ad": "Golf",
                    "doc_count": 2,
                    "page_count": 8,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "harpsichord",
                    "area": "blue",
                    "ad": "Hotel",
                    "doc_count": 2,
                    "page_count": 22,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "oboe",
                    "area": "blue",
                    "ad": "Indigo",
                    "doc_count": 2,
                    "page_count": 8,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "organ",
                    "area": "blue",
                    "ad": "Indigo",
                    "doc_count": 2,
                    "page_count": 10,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "piano",
                    "area": "violet",
                    "ad": "Juliet",
                    "doc_count": 2,
                    "page_count": 10,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "piccolo",
                    "area": "violet",
                    "ad": "Kilo",
                    "doc_count": 2,
                    "page_count": 14,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "saxophone",
                    "area": "violet",
                    "ad": "Lima",
                    "doc_count": 4,
                    "page_count": 36,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "tambourine",
                    "area": "violet",
                    "ad": "Lima",
                    "doc_count": 2,
                    "page_count": 20,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
                {
                    "wg": "timpani",
                    "area": "orange",
                    "ad": "Juliet",
                    "doc_count": 2,
                    "page_count": 14,
                    "rfc_count": 0,
                    "recent_rfc_count": 0,
                },
            ],
        )

        # Make sure the view doesn't _crash_ - the template is a dead-simple rendering of the dicts, but this test doesn't prove that
        url = urlreverse("ietf.iesg.views.working_groups")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)


class IESGAgendaTests(TestCase):
    def setUp(self):
        super().setUp()
        mars = GroupFactory(acronym='mars',parent=Group.objects.get(acronym='farfut'))
        wgdraft = WgDraftFactory(name='draft-ietf-mars-test', group=mars, intended_std_level_id='ps')
        rfc = IndividualRfcFactory.create(stream_id='irtf', rfc_number=6666, std_level_id='inf', )
        wgdraft.relateddocument_set.create(target=rfc, relationship_id='refnorm')
        ise_draft = IndividualDraftFactory(name='draft-imaginary-independent-submission')
        ise_draft.stream = StreamName.objects.get(slug="ise")
        ise_draft.save_with_history([DocEvent(doc=ise_draft, rev=ise_draft.rev, type="changed_stream", by=Person.objects.get(user__username="secretary"), desc="Test")])
        ConflictReviewFactory(name='conflict-review-imaginary-irtf-submission', review_of=ise_draft)
        BaseDocumentFactory(type_id='statchg',name='status-change-imaginary-mid-review')
        WgRfcFactory(std_level_id='inf')
        WgRfcFactory(std_level_id='ps')
        CharterFactory(states=[('charter','iesgrev')])

        self.telechat_docs = {
            "ietf_draft": Document.objects.get(name="draft-ietf-mars-test"),
            "ise_draft": ise_draft,
            "conflrev": Document.objects.get(name="conflict-review-imaginary-irtf-submission"),
            "statchg": Document.objects.get(name="status-change-imaginary-mid-review"),
            "charter": Document.objects.filter(type="charter")[0],
            }

        by = Person.objects.get(name="Areað Irector")
        date = get_agenda_date()

        for d in list(self.telechat_docs.values()):
            TelechatDocEvent.objects.create(type="scheduled_for_telechat",
                                            doc=d,
                                            rev=d.rev,
                                            by=by,
                                            telechat_date=date,
                                            returning_item=True)

        self.mgmt_items = [ ]
        for i in range(0, 10):
            self.mgmt_items.append(IESGMgmtItemFactory())

    def test_fill_in_agenda_administrivia(self):
        roll_call = TelechatAgendaContentFactory(section_id='roll_call')
        minutes = TelechatAgendaContentFactory(section_id='minutes')
        action_items = TelechatAgendaContentFactory(section_id='action_items')
        sections = agenda_sections()
        fill_in_agenda_administrivia(None, sections)  # n.b., date parameter is unused at present
        self.assertIn(roll_call.text, sections["1.1"]["text"])
        self.assertIn(minutes.text, sections["1.3"]["text"])
        self.assertIn(action_items.text, sections["1.4"]["text"])

    def test_fill_in_agenda_docs(self):
        draft = self.telechat_docs["ietf_draft"]
        statchg = self.telechat_docs["statchg"]
        conflrev = self.telechat_docs["conflrev"]
        charter = self.telechat_docs["charter"]
        mgmtitem = self.mgmt_items

        # put on agenda
        date = date_today(settings.TIME_ZONE) + datetime.timedelta(days=50)
        TelechatDate.objects.create(date=date)
        telechat_event = TelechatDocEvent.objects.create(
            type="scheduled_for_telechat",
            doc=draft,
            rev=draft.rev,
            by=Person.objects.get(name="Areað Irector"),
            telechat_date=date,
            returning_item=False)
        date_str = date.isoformat()

        # 2.1 protocol WG submissions
        draft.intended_std_level_id = "ps"
        draft.group = GroupFactory(acronym="mars")
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.1.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.1.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        draft.set_state(State.objects.get(type="draft-iesg", slug="pub-req"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.1.3"]["docs"])

        # 2.2 protocol individual submissions
        draft.group = Group.objects.get(type="individ")
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.2.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.2.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        draft.set_state(State.objects.get(type="draft-iesg", slug="pub-req"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["2.2.3"]["docs"])

        # 3.1 document WG submissions
        draft.intended_std_level_id = "inf"
        draft.group = Group.objects.get(acronym="mars")
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.1.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.1.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        draft.set_state(State.objects.get(type="draft-iesg", slug="pub-req"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.1.3"]["docs"])

        # 3.2 document individual submissions
        draft.group = Group.objects.get(type="individ")
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.2.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.2.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        draft.set_state(State.objects.get(type="draft-iesg", slug="pub-req"))
        self.assertTrue(draft in agenda_data(date_str)["sections"]["3.2.3"]["docs"])

        # 2.3 protocol status changes
        telechat_event.doc = statchg
        telechat_event.save()

        relation = RelatedDocument.objects.create(
            source=statchg,
            target=Document.objects.filter(type_id="rfc", std_level="ps").first(),
            relationship_id="tohist")

        statchg.group = Group.objects.get(acronym="mars")
        statchg.save_with_history([DocEvent.objects.create(doc=statchg, rev=statchg.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        statchg.set_state(State.objects.get(type="statchg", slug="iesgeval"))
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["2.3.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["2.3.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        statchg.set_state(State.objects.get(type="statchg", slug="adrev"))
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["2.3.3"]["docs"])
        
        # 3.3 document status changes
        relation.target = Document.objects.filter(type_id="rfc", std_level="inf").first()
        relation.save()

        statchg.group = Group.objects.get(acronym="mars")
        statchg.save_with_history([DocEvent.objects.create(doc=statchg, rev=statchg.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        statchg.set_state(State.objects.get(type="statchg", slug="iesgeval"))
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["3.3.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["3.3.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        statchg.set_state(State.objects.get(type="statchg", slug="adrev"))
        self.assertTrue(statchg in agenda_data(date_str)["sections"]["3.3.3"]["docs"])

        # 3.4 IRTF/ISE conflict reviews
        telechat_event.doc = conflrev
        telechat_event.save()

        conflrev.group = Group.objects.get(acronym="mars")
        conflrev.save_with_history([DocEvent.objects.create(doc=conflrev, rev=conflrev.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])
        conflrev.set_state(State.objects.get(type="conflrev", slug="iesgeval"))
        self.assertTrue(conflrev in agenda_data(date_str)["sections"]["3.4.1"]["docs"])

        telechat_event.returning_item = True
        telechat_event.save()
        self.assertTrue(conflrev in agenda_data(date_str)["sections"]["3.4.2"]["docs"])

        telechat_event.returning_item = False
        telechat_event.save()
        conflrev.set_state(State.objects.get(type="conflrev", slug="needshep"))
        self.assertTrue(conflrev in agenda_data(date_str)["sections"]["3.4.3"]["docs"])

        # 4 WGs
        telechat_event.doc = charter
        telechat_event.save()

        charter.group = Group.objects.get(acronym="mars")
        charter.save_with_history([DocEvent.objects.create(doc=charter, rev=charter.rev, type="changed_group", by=Person.objects.get(user__username="secretary"), desc="Test")])

        charter.group.state_id = "bof"
        charter.group.save()

        charter.set_state(State.objects.get(type="charter", slug="infrev"))
        self.assertTrue(charter in agenda_data(date_str)["sections"]["4.1.1"]["docs"])

        charter.set_state(State.objects.get(type="charter", slug="iesgrev"))
        self.assertTrue(charter in agenda_data(date_str)["sections"]["4.1.2"]["docs"])

        charter.group.state_id = "active"
        charter.group.save()

        charter.set_state(State.objects.get(type="charter", slug="infrev"))
        self.assertTrue(charter in agenda_data(date_str)["sections"]["4.2.1"]["docs"])

        charter.set_state(State.objects.get(type="charter", slug="iesgrev"))
        self.assertTrue(charter in agenda_data(date_str)["sections"]["4.2.2"]["docs"])

        #for n, s in agenda_data(date_str)["sections"].iteritems():
        #    print n, s.get("docs") if "docs" in s else s["title"]

        # 10 Management Items
        for i, mi in enumerate(mgmtitem, start=1):
            s = "6." + str(i)
            self.assertEqual(mi.title, agenda_data(date_str)["sections"][s]['title'])

    def test_feed(self):
        r = self.client.get("/feed/iesg-agenda/")
        self.assertEqual(r.status_code, 200)

        for d in list(self.telechat_docs.values()):
            self.assertContains(r, d.name)
            self.assertContains(r, d.title)

    def test_agenda_json(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda_json"))
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            if d.type_id == "charter":
                self.assertContains(r, d.group.name, msg_prefix="%s '%s' not in response" % (k, d.group.name))
                self.assertContains(r, d.group.acronym, msg_prefix="%s '%s' acronym not in response" % (k, d.group.acronym))
            else:
                self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name))
                self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title))

        self.assertTrue(r.json())

    def test_agenda(self):
        action_items = TelechatAgendaContentFactory(section_id='action_items')
        r = self.client.get(urlreverse("ietf.iesg.views.agenda"))
        self.assertEqual(r.status_code, 200)

        self.assertContains(r, action_items.text)

        q = PyQuery(r.content)

        for k, d in self.telechat_docs.items():
            if d.type_id == "charter":
                self.assertContains(r, d.group.name, msg_prefix="%s '%s' not in response" % (k, d.group.name))
                self.assertContains(r, d.group.acronym, msg_prefix="%s '%s' acronym not in response" % (k, d.group.acronym))
            else:
                self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name))
                self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title))

            if d.type_id in ["charter", "draft"]:
                if d.group.parent is None:
                    continue
                wg_url = urlreverse("ietf.group.views.active_groups", kwargs=dict(group_type="wg"))
                href = f"{wg_url}#{d.group.parent.acronym.upper()}"
                texts = [elem.text.strip() for elem in q(f'a[href="{href}"]')]
                self.assertGreater(len(texts), 0)
                if d.type_id == "charter":
                    self.assertTrue(any(t == d.group.parent.acronym.upper() for t in texts))
                elif d.type_id == "draft":
                    self.assertTrue(any(t == f"({d.group.parent.acronym.upper()})" for t in texts))

        for i, mi in enumerate(self.mgmt_items, start=1):
            s = "6." + str(i)
            self.assertContains(r, s, msg_prefix="Section '%s' not in response" % s)
            self.assertContains(r, mi.title, msg_prefix="Management item title '%s' not in response" % mi.title)

        # Make sure the sort places 6.9 before 6.10
        self.assertLess(r.content.find(b"6.9"), r.content.find(b"6.10"))

    def test_agenda_restricted_sections(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda"))
        # not logged in
        for section_id in ("roll_call", "minutes"):
            self.assertNotContains(
                r, urlreverse("ietf.iesg.views.telechat_agenda_content_view", kwargs={"section": section_id})
            )

        self.client.login(username="plain", password="plain+password")
        for section_id in ("roll_call", "minutes"):
            self.assertNotContains(
                r, urlreverse("ietf.iesg.views.telechat_agenda_content_view", kwargs={"section": section_id})
            )

        for username in ("ad", "secretary", "iab chair"):
            self.client.login(username=username, password=f"{username}+password")
            r = self.client.get(urlreverse("ietf.iesg.views.agenda"))
            self.assertEqual(r.status_code, 200)
            for section_id in ("roll_call", "minutes"):
                self.assertContains(
                    r, urlreverse("ietf.iesg.views.telechat_agenda_content_view", kwargs={"section": section_id})
                )

    def test_agenda_txt(self):
        r = self.client.get(urlreverse("ietf.iesg.views.agenda_txt"))
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            if d.type_id == "charter":
                self.assertContains(r, d.group.name, msg_prefix="%s '%s' not in response" % (k, d.group.name))
                self.assertContains(r, d.group.acronym, msg_prefix="%s '%s' acronym not in response" % (k, d.group.acronym))
            else:
                self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name))
                self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title))

        for i, mi in enumerate(self.mgmt_items, start=1):
            s = "6." + str(i)
            self.assertContains(r, s, msg_prefix="Section '%s' not in response" % s)
            self.assertContains(r, mi.title, msg_prefix="Management item title '%s' not in response" % mi.title)

        # Make sure the sort places 6.9 before 6.10
        self.assertLess(r.content.find(b"6.9"), r.content.find(b"6.10"))

    def test_agenda_moderator_package(self):
        url = urlreverse("ietf.iesg.views.agenda_moderator_package")
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            if d.type_id == "charter":
                self.assertContains(r, d.group.name, msg_prefix="%s '%s' not in response" % (k, d.group.name))
                self.assertContains(r, d.group.acronym, msg_prefix="%s '%s' acronym not in response" % (k, d.group.acronym))
            else:
                if d.type_id == "draft" and d.name == "draft-ietf-mars-test":
                    self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name))
                    self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title))
                    self.assertContains(r, "Has downref: Yes", msg_prefix="%s downref not in response" % (k, ))
                    self.assertContains(r, "Add rfc6666", msg_prefix="%s downref not in response" % (k, ))
                else:
                    self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name))
                    self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title))        

    def test_agenda_package(self):
        url = urlreverse("ietf.iesg.views.agenda_package")
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            if d.type_id == "charter":
                self.assertContains(r, d.group.name, msg_prefix="%s '%s' not in response" % (k, d.group.name, ))
                self.assertContains(r, d.group.acronym, msg_prefix="%s '%s' acronym not in response" % (k, d.group.acronym, ))
            else:
                self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name, ))
                self.assertContains(r, d.title, msg_prefix="%s '%s' title not in response" % (k, d.title, ))

    def test_agenda_documents_txt(self):
        url = urlreverse("ietf.iesg.views.agenda_documents_txt")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name, ))

    def test_agenda_documents(self):
        url = urlreverse("ietf.iesg.views.agenda_documents")
        r = self.client.get(url)

        self.assertEqual(r.status_code, 200)

        for k, d in self.telechat_docs.items():
            self.assertContains(r, d.name, msg_prefix="%s '%s' not in response" % (k, d.name, ))
            self.assertContains(r, d.title, msg_prefix="%s '%s' not in response" % (k, d.title, ))
    
    def test_past_documents(self):
        url = urlreverse("ietf.iesg.views.past_documents")
        # We haven't put any documents on past telechats, so this should be empty
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        for k, d in self.telechat_docs.items():
            self.assertNotIn(d.name, unicontent(r))
            self.assertNotIn(d.title, unicontent(r))
        # Add the documents to a past telechat
        by = Person.objects.get(name="Areað Irector")
        date = date_today(settings.TIME_ZONE) - datetime.timedelta(days=14)
        approved = State.objects.get(type='draft-iesg', slug='approved')
        iesg_eval = State.objects.get(type='draft-iesg', slug='iesg-eva')
        for d in list(self.telechat_docs.values()):
            if d.type_id in ['draft', 'charter']:
                create_ballot_if_not_open(None, d, by, 'approve')
            TelechatDocEvent.objects.create(type="scheduled_for_telechat",
                doc=d, rev=d.rev, by=by, telechat_date=date, returning_item=False)
            s = d.get_state('draft-iesg')
            d.states.clear()
            if s and s.slug == 'pub-req':
                d.states.add(iesg_eval)
            else:
                d.states.add(approved)
        # Now check that they are present on the past documents page
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        for k, d in self.telechat_docs.items():
            if d.states.get(type='draft-iesg').slug in ['approved', 'iesg-eva', ]:
                self.assertIn(d.name, unicontent(r))
            else:
                self.assertNotIn(d.name, unicontent(r))

    def test_agenda_telechat_docs(self):
        d1 = self.telechat_docs["ietf_draft"]
        d2 = self.telechat_docs["ise_draft"]

        d1_filename = "%s-%s.txt" % (d1.name, d1.rev)
        d2_filename = "%s-%s.txt" % (d2.name, d2.rev)

        with (Path(settings.INTERNET_DRAFT_PATH) / d1_filename).open("w") as f:
            f.write("test content")

        url = urlreverse("ietf.iesg.views.telechat_docs_tarfile", kwargs=dict(date=get_agenda_date().isoformat()))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        tar = tarfile.open(None, fileobj=io.BytesIO(r.content))
        names = tar.getnames()
        self.assertIn(d1_filename, names)
        self.assertNotIn(d2_filename, names)
        self.assertIn("manifest.txt", names)

        f = tar.extractfile(d1_filename)
        self.assertEqual(f.read(), b"test content")

        f = tar.extractfile("manifest.txt")
        lines = list(f.readlines())
        d1fn = force_bytes(d1_filename)
        d2fn = force_bytes(d2_filename)
        self.assertTrue(b"Included" in [l for l in lines if d1fn in l][0])
        self.assertTrue(b"Not found" in [l for l in lines if d2fn in l][0])

    def test_admin_change(self):
        draft = Document.objects.get(name="draft-ietf-mars-test")
        today = date_today(settings.TIME_ZONE)
        telechat_date = TelechatDate.objects.get(date=draft.telechat_date())
        url = urlreverse('admin:iesg_telechatdate_change', args=(telechat_date.id,))
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, {'initial-date': telechat_date.date.strftime('%Y-%m-%d'), 'date':today.strftime('%Y-%m-%d')})
        self.assertRedirects(r, urlreverse('admin:iesg_telechatdate_changelist'))
        draft = Document.objects.get(name="draft-ietf-mars-test")
        self.assertEqual(draft.telechat_date(),today)

class IESGAgendaTelechatPagesTests(TestCase):
    def setUp(self):
        super().setUp()
        # make_immutable_test_data made a set of future telechats - only need one
        # We'll take the "next" one
        self.telechat_date = get_agenda_date()
        # make_immutable_test_data made and area with only one ad - give it another
        ad = Person.objects.get(user__username="ad")
        adrole = Role.objects.get(person=ad, name="ad")
        ad2 = RoleFactory(group=adrole.group, name_id="ad").person
        self.ads=[ad,ad2]
        
        # Make some drafts
        docs = [
            WgDraftFactory(pages=2, states=[('draft-iesg','iesg-eva'),]),
            IndividualDraftFactory(pages=20, states=[('draft-iesg','iesg-eva'),]),
            WgDraftFactory(pages=200, states=[('draft-iesg','iesg-eva'),]),
        ]
        # Put them on the telechat
        for doc in docs:
            TelechatDocEventFactory(doc=doc, telechat_date=self.telechat_date)
        # Give them ballots
        ballots = [BallotDocEventFactory(doc=doc) for doc in docs]

        # Give the "ad" Area-Director a discuss on one 
        BallotPositionDocEventFactory(balloter=ad, doc=docs[0], pos_id="discuss", ballot=ballots[0])
        # and a "norecord" position on another
        BallotPositionDocEventFactory(balloter=ad, doc=docs[1], pos_id="norecord", ballot=ballots[1])
        # Now "ad" should have 220 pages left to ballot on.
        # Every other ad should have 222 pages left to ballot on.

    def test_ad_pages_left_to_ballot_on(self):
        url = urlreverse("ietf.iesg.views.agenda_documents")

        # A non-AD user won't get "pages left"
        response = self.client.get(url)
        telechat = response.context["telechats"][0]
        self.assertEqual(telechat["date"], self.telechat_date)
        self.assertEqual(telechat["ad_pages_left_to_ballot_on"],0)
        self.assertNotContains(response,"pages left to ballot on")

        username=self.ads[0].user.username
        self.assertTrue(self.client.login(username=username, password=f"{username}+password"))

        response = self.client.get(url)
        telechat = response.context["telechats"][0]
        self.assertEqual(telechat["ad_pages_left_to_ballot_on"],220)
        self.assertContains(response,"220 pages left to ballot on")

        self.client.logout()
        username=self.ads[1].user.username
        self.assertTrue(self.client.login(username=username, password=f"{username}+password"))

        response = self.client.get(url)
        telechat = response.context["telechats"][0]
        self.assertEqual(telechat["ad_pages_left_to_ballot_on"],222)




class RescheduleOnAgendaTests(TestCase):
    def test_reschedule(self):
        draft = WgDraftFactory()

        # add to schedule
        e = TelechatDocEvent(type="scheduled_for_telechat")
        e.doc = draft
        e.rev = draft.rev
        e.by = Person.objects.get(name="Areað Irector")
        e.telechat_date = TelechatDate.objects.active()[0].date
        e.returning_item = True
        e.save()
        
        form_id = draft.name
        
        url = urlreverse('ietf.iesg.views.agenda_documents')
        
        self.client.login(username="secretary", password="secretary+password")

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=%s-telechat_date]' % form_id)), 1)
        self.assertEqual(len(q('form input[name=%s-clear_returning_item]' % form_id)), 1)

        # reschedule
        events_before = draft.docevent_set.count()
        d = TelechatDate.objects.active()[3].date

        r = self.client.post(url, { '%s-telechat_date' % form_id: d.isoformat(),
                                    '%s-clear_returning_item' % form_id: "1" })

        self.assertEqual(r.status_code, 302)

        # check that it moved below the right header in the DOM on the
        # agenda docs page
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        d_header_pos = content.find("IESG telechat %s" % d.isoformat())
        draft_pos = content[d_header_pos:].find(draft.name)
        self.assertTrue(draft_pos>0)

        self.assertTrue(draft.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        self.assertEqual(draft.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date, d)
        self.assertTrue(not draft.latest_event(TelechatDocEvent, "scheduled_for_telechat").returning_item)
        self.assertEqual(draft.docevent_set.count(), events_before + 1)


class TelechatAgendaContentTests(TestCase):
    def test_telechat_agenda_content_view(self):
        self.client.login(username="ad", password="ad+password")
        r = self.client.get(urlreverse("ietf.iesg.views.telechat_agenda_content_view", kwargs={"section": "fake"}))
        self.assertEqual(r.status_code, 404, "Nonexistent section should 404")
        for section in TelechatAgendaSectionName.objects.filter(used=True).values_list("slug", flat=True):
            r = self.client.get(
                urlreverse("ietf.iesg.views.telechat_agenda_content_view", kwargs={"section": section})
            )
            self.assertEqual(r.status_code, 404, "Section with no content should 404")
        for section in TelechatAgendaSectionName.objects.filter(used=True).values_list("slug", flat=True):
            content = TelechatAgendaContentFactory(section_id=section).text
            r = self.client.get(
                urlreverse("ietf.iesg.views.telechat_agenda_content_view", kwargs={"section": section})
            )
            self.assertContains(r, content, status_code=200)
            self.assertEqual(r.get("Content-Type", None), "text/plain; charset=utf-8")

    def test_telechat_agenda_content_view_permissions(self):
        for section in TelechatAgendaSectionName.objects.filter(used=True).values_list("slug", flat=True):
            TelechatAgendaContentFactory(section_id=section)
            url = urlreverse("ietf.iesg.views.telechat_agenda_content_view", kwargs={"section": section})
            self.client.logout()
            login_testing_unauthorized(self, "plain", url)
            login_testing_unauthorized(self, "ad", url)
            self.assertEqual(self.client.get(url).status_code, 200)
            self.client.login(username="iab chair", password="iab chair+password")
            self.assertEqual(self.client.get(url).status_code, 200)
            self.client.login(username="secretary", password="secretary+password")
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_telechat_agenda_content_edit(self):
        for section in TelechatAgendaSectionName.objects.filter(used=True):
            self.assertFalse(TelechatAgendaContent.objects.filter(section=section).exists())
            url = urlreverse("ietf.iesg.views.telechat_agenda_content_edit", kwargs={"section": section.slug})
            self.client.logout()
            login_testing_unauthorized(self, "plain", url, method="get")
            login_testing_unauthorized(self, "ad", url, method="get")
            login_testing_unauthorized(self, "iab chair", url, method="get")
            login_testing_unauthorized(self, "secretary", url, method="get")
            r = self.client.get(url)
            self.assertContains(r, str(section), status_code=200)

            self.client.logout()
            login_testing_unauthorized(self, "plain", url, method="post")
            login_testing_unauthorized(self, "ad", url, method="post")
            login_testing_unauthorized(self, "iab chair", url, method="post")
            login_testing_unauthorized(self, "secretary", url, method="post")
            r = self.client.post(url, {"text": "This is some content"})
            self.assertRedirects(r, urlreverse("ietf.iesg.views.telechat_agenda_content_manage"))
            contents = TelechatAgendaContent.objects.filter(section=section)
            self.assertEqual(contents.count(), 1)
            self.assertEqual(contents.first().text, "This is some content")

            self.client.logout()
            login_testing_unauthorized(self, "plain", url, method="post")
            login_testing_unauthorized(self, "ad", url, method="post")
            login_testing_unauthorized(self, "iab chair", url, method="post")
            login_testing_unauthorized(self, "secretary", url, method="post")
            r = self.client.post(url, {"text": "This is some different content"})
            self.assertRedirects(r, urlreverse("ietf.iesg.views.telechat_agenda_content_manage"))
            contents = TelechatAgendaContent.objects.filter(section=section)
            self.assertEqual(contents.count(), 1)
            self.assertEqual(contents.first().text, "This is some different content")

    def test_telechat_agenda_content_manage(self):
        url = urlreverse("ietf.iesg.views.telechat_agenda_content_manage")
        login_testing_unauthorized(self, "plain", url)
        login_testing_unauthorized(self, "ad", url)
        login_testing_unauthorized(self, "iab chair", url)
        login_testing_unauthorized(self, "secretary", url)
        self.assertEqual(TelechatAgendaContent.objects.count(), 0)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        pq = PyQuery(r.content)
        for section in TelechatAgendaSectionName.objects.filter(used=True):
            # check that there's a tab even when section is empty
            nav_button = pq(f"button.nav-link#{section.slug}-tab")
            self.assertEqual(nav_button.text(), str(section))
            edit_url = urlreverse("ietf.iesg.views.telechat_agenda_content_edit", kwargs={"section": section.pk})
            edit_button = pq(f'div#{section.slug} a[href="{edit_url}"]')
            self.assertEqual(len(edit_button), 1)
            self.assertIn(f"No {section}", pq(f"div#{section.slug}").text())
            # and create a section for the next test
            TelechatAgendaContentFactory(section_id=section.slug)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        pq = PyQuery(r.content)
        for section in TelechatAgendaSectionName.objects.filter(used=True):
            # check that there's a tab with the content
            nav_button = pq(f"button.nav-link#{section.slug}-tab")
            self.assertEqual(nav_button.text(), str(section))
            edit_url = urlreverse("ietf.iesg.views.telechat_agenda_content_edit", kwargs={"section": section.pk})
            edit_button = pq(f'div#{section.slug} a[href="{edit_url}"]')
            self.assertEqual(len(edit_button), 1)
            self.assertIn(
                TelechatAgendaContent.objects.get(section=section).text, pq(f"div#{section.slug}").text()
            )

