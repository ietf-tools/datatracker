# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from pyquery import PyQuery

from django.urls import reverse as urlreverse
from django.contrib.auth.models import User

from django_webtest import WebTest

import debug                            # pyflakes:ignore

from ietf.community.models import CommunityList, SearchRule, EmailSubscription
from ietf.community.utils import docs_matching_community_list_rule, community_list_rules_matching_doc
from ietf.community.utils import reset_name_contains_index_for_rule
import ietf.community.views
from ietf.group.models import Group
from ietf.group.utils import setup_default_community_list_for_group
from ietf.doc.models import State
from ietf.doc.utils import add_state_change_event
from ietf.person.models import Person, Email
from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.mail import outbox
from ietf.doc.factories import WgDraftFactory
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.person.factories import PersonFactory

class CommunityListTests(WebTest):
    def test_rule_matching(self):
        plain = PersonFactory(user__username='plain')
        ad = Person.objects.get(user__username='ad')
        draft = WgDraftFactory(
            group__parent=Group.objects.get(acronym='farfut' ),
            authors=[ad],
            ad=ad,
            shepherd=plain.email(),
            states=[('draft-iesg','lc'),('draft','active')],
        )

        clist = CommunityList.objects.create(user=User.objects.get(username="plain"))

        rule_group = SearchRule.objects.create(rule_type="group", group=draft.group, state=State.objects.get(type="draft", slug="active"), community_list=clist)
        rule_group_rfc = SearchRule.objects.create(rule_type="group_rfc", group=draft.group, state=State.objects.get(type="draft", slug="rfc"), community_list=clist)
        rule_area = SearchRule.objects.create(rule_type="area", group=draft.group.parent, state=State.objects.get(type="draft", slug="active"), community_list=clist)

        rule_state_iesg = SearchRule.objects.create(rule_type="state_iesg", state=State.objects.get(type="draft-iesg", slug="lc"), community_list=clist)

        rule_author = SearchRule.objects.create(rule_type="author", state=State.objects.get(type="draft", slug="active"), person=Person.objects.filter(documentauthor__document=draft).first(), community_list=clist)

        rule_ad = SearchRule.objects.create(rule_type="ad", state=State.objects.get(type="draft", slug="active"), person=draft.ad, community_list=clist)

        rule_shepherd = SearchRule.objects.create(rule_type="shepherd", state=State.objects.get(type="draft", slug="active"), person=draft.shepherd.person, community_list=clist)

        rule_name_contains = SearchRule.objects.create(rule_type="name_contains", state=State.objects.get(type="draft", slug="active"), text="draft-.*" + "-".join(draft.name.split("-")[2:]), community_list=clist)
        reset_name_contains_index_for_rule(rule_name_contains)

        # doc -> rules
        matching_rules = list(community_list_rules_matching_doc(draft))
        self.assertTrue(rule_group in matching_rules)
        self.assertTrue(rule_group_rfc not in matching_rules)
        self.assertTrue(rule_area in matching_rules)
        self.assertTrue(rule_state_iesg in matching_rules)
        self.assertTrue(rule_author in matching_rules)
        self.assertTrue(rule_ad in matching_rules)
        self.assertTrue(rule_shepherd in matching_rules)
        self.assertTrue(rule_name_contains in matching_rules)

        # rule -> docs
        self.assertTrue(draft in list(docs_matching_community_list_rule(rule_group)))
        self.assertTrue(draft not in list(docs_matching_community_list_rule(rule_group_rfc)))
        self.assertTrue(draft in list(docs_matching_community_list_rule(rule_area)))
        self.assertTrue(draft in list(docs_matching_community_list_rule(rule_state_iesg)))
        self.assertTrue(draft in list(docs_matching_community_list_rule(rule_author)))
        self.assertTrue(draft in list(docs_matching_community_list_rule(rule_ad)))
        self.assertTrue(draft in list(docs_matching_community_list_rule(rule_shepherd)))
        self.assertTrue(draft in list(docs_matching_community_list_rule(rule_name_contains)))

    def test_view_list(self):
        PersonFactory(user__username='plain')
        draft = WgDraftFactory()

        url = urlreverse(ietf.community.views.view_list, kwargs={ "username": "plain" })

        # without list
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # with list
        clist = CommunityList.objects.create(user=User.objects.get(username="plain"))
        if not draft in clist.added_docs.all():
            clist.added_docs.add(draft)
        SearchRule.objects.create(
            community_list=clist,
            rule_type="name_contains",
            state=State.objects.get(type="draft", slug="active"),
            text="test",
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.name)

    def test_manage_personal_list(self):
        PersonFactory(user__username='plain')
        ad = Person.objects.get(user__username='ad')
        draft = WgDraftFactory(authors=[ad])

        url = urlreverse(ietf.community.views.manage_list, kwargs={ "username": "plain" })
        login_testing_unauthorized(self, "plain", url)

        page = self.app.get(url, user='plain')
        self.assertEqual(page.status_int, 200)

        # add document
        self.assertIn('add_document', page.forms)
        form = page.forms['add_document']
        form['documents']=draft.pk
        page = form.submit('action',value='add_documents')
        self.assertEqual(page.status_int, 302)
        clist = CommunityList.objects.get(user__username="plain")
        self.assertTrue(clist.added_docs.filter(pk=draft.pk))        
        page = page.follow()

        self.assertContains(page, draft.name)

        # remove document
        self.assertIn('remove_document_%s' % draft.pk, page.forms)
        form = page.forms['remove_document_%s' % draft.pk]
        page = form.submit('action',value='remove_document')
        self.assertEqual(page.status_int, 302)
        clist = CommunityList.objects.get(user__username="plain")
        self.assertTrue(not clist.added_docs.filter(pk=draft.pk))
        page = page.follow()
        
        # add rule
        r = self.client.post(url, {
            "action": "add_rule",
            "rule_type": "author_rfc",
            "author_rfc-person": Person.objects.filter(documentauthor__document=draft).first().pk,
            "author_rfc-state": State.objects.get(type="draft", slug="rfc").pk,
        })
        self.assertEqual(r.status_code, 302)
        clist = CommunityList.objects.get(user__username="plain")
        self.assertTrue(clist.searchrule_set.filter(rule_type="author_rfc"))

        # add name_contains rule
        r = self.client.post(url, {
            "action": "add_rule",
            "rule_type": "name_contains",
            "name_contains-text": "draft.*mars",
            "name_contains-state": State.objects.get(type="draft", slug="active").pk,
        })
        self.assertEqual(r.status_code, 302)
        clist = CommunityList.objects.get(user__username="plain")
        self.assertTrue(clist.searchrule_set.filter(rule_type="name_contains"))

        # rule shows up on GET
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        rule = clist.searchrule_set.filter(rule_type="author_rfc").first()
        q = PyQuery(r.content)
        self.assertEqual(len(q('#r%s' % rule.pk)), 1)

        # remove rule
        r = self.client.post(url, {
            "action": "remove_rule",
            "rule": rule.pk,
        })

        clist = CommunityList.objects.get(user__username="plain")
        self.assertTrue(not clist.searchrule_set.filter(rule_type="author_rfc"))

    def test_manage_group_list(self):
        draft = WgDraftFactory(group__acronym='mars')
        RoleFactory(group__acronym='mars',name_id='chair',person=PersonFactory(user__username='marschairman'))

        url = urlreverse(ietf.community.views.manage_list, kwargs={ "acronym": draft.group.acronym })
        setup_default_community_list_for_group(draft.group)
        login_testing_unauthorized(self, "marschairman", url)

        # test GET, rest is tested with personal list
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # Verify GET also works with non-WG and RG groups
        for gtype in ['area','program']:
            g = GroupFactory.create(type_id=gtype)
            # make sure the group's features have been initialized to improve coverage
            _ = g.features # pyflakes:ignore
            p = PersonFactory()
            g.role_set.create(name_id={'area':'ad','program':'lead'}[gtype],person=p, email=p.email())
            url = urlreverse(ietf.community.views.manage_list, kwargs={ "acronym": g.acronym })
            setup_default_community_list_for_group(g)
            self.client.login(username=p.user.username,password=p.user.username+"+password")
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)

    def test_track_untrack_document(self):
        PersonFactory(user__username='plain')
        draft = WgDraftFactory()

        url = urlreverse(ietf.community.views.track_document, kwargs={ "username": "plain", "name": draft.name })
        login_testing_unauthorized(self, "plain", url)

        # track
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)
        clist = CommunityList.objects.get(user__username="plain")
        self.assertEqual(list(clist.added_docs.all()), [draft])

        # untrack
        url = urlreverse(ietf.community.views.untrack_document, kwargs={ "username": "plain", "name": draft.name })
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)
        clist = CommunityList.objects.get(user__username="plain")
        self.assertEqual(list(clist.added_docs.all()), [])

    def test_track_untrack_document_through_ajax(self):
        PersonFactory(user__username='plain')
        draft = WgDraftFactory()

        url = urlreverse(ietf.community.views.track_document, kwargs={ "username": "plain", "name": draft.name })
        login_testing_unauthorized(self, "plain", url)

        # track
        r = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["success"], True)
        clist = CommunityList.objects.get(user__username="plain")
        self.assertEqual(list(clist.added_docs.all()), [draft])

        # untrack
        url = urlreverse(ietf.community.views.untrack_document, kwargs={ "username": "plain", "name": draft.name })
        r = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["success"], True)
        clist = CommunityList.objects.get(user__username="plain")
        self.assertEqual(list(clist.added_docs.all()), [])

    def test_csv(self):
        PersonFactory(user__username='plain')
        draft = WgDraftFactory()

        url = urlreverse(ietf.community.views.export_to_csv, kwargs={ "username": "plain" })

        # without list
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # with list
        clist = CommunityList.objects.create(user=User.objects.get(username="plain"))
        if not draft in clist.added_docs.all():
            clist.added_docs.add(draft)
        SearchRule.objects.create(
            community_list=clist,
            rule_type="name_contains",
            state=State.objects.get(type="draft", slug="active"),
            text="test",
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # this is a simple-minded test, we don't actually check the fields
        self.assertContains(r, draft.name)

    def test_csv_for_group(self):
        draft = WgDraftFactory()

        url = urlreverse(ietf.community.views.export_to_csv, kwargs={ "acronym": draft.group.acronym })

        setup_default_community_list_for_group(draft.group)

        # test GET, rest is tested with personal list
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_feed(self):
        PersonFactory(user__username='plain')
        draft = WgDraftFactory()

        url = urlreverse(ietf.community.views.feed, kwargs={ "username": "plain" })

        # without list
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # with list
        clist = CommunityList.objects.create(user=User.objects.get(username="plain"))
        if not draft in clist.added_docs.all():
            clist.added_docs.add(draft)
        SearchRule.objects.create(
            community_list=clist,
            rule_type="name_contains",
            state=State.objects.get(type="draft", slug="active"),
            text="test",
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.name)

        # only significant
        r = self.client.get(url + "?significant=1")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, '<entry>')

    def test_feed_for_group(self):
        draft = WgDraftFactory()

        url = urlreverse(ietf.community.views.feed, kwargs={ "acronym": draft.group.acronym })

        setup_default_community_list_for_group(draft.group)

        # test GET, rest is tested with personal list
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        
    def test_subscription(self):
        PersonFactory(user__username='plain')
        draft = WgDraftFactory()

        url = urlreverse(ietf.community.views.subscription, kwargs={ "username": "plain" })

        login_testing_unauthorized(self, "plain", url)

        # subscription without list
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        # subscription with list
        clist = CommunityList.objects.create(user=User.objects.get(username="plain"))
        if not draft in clist.added_docs.all():
            clist.added_docs.add(draft)
        SearchRule.objects.create(
            community_list=clist,
            rule_type="name_contains",
            state=State.objects.get(type="draft", slug="active"),
            text="test",
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # subscribe
        email = Email.objects.filter(person__user__username="plain").first()
        r = self.client.post(url, { "email": email.pk, "notify_on": "significant", "action": "subscribe" })
        self.assertEqual(r.status_code, 302)

        subscription = EmailSubscription.objects.filter(community_list=clist, email=email, notify_on="significant").first()

        self.assertTrue(subscription)

        # delete subscription
        r = self.client.post(url, { "subscription_id": subscription.pk, "action": "unsubscribe" })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(EmailSubscription.objects.filter(community_list=clist, email=email, notify_on="significant").count(), 0)

    def test_subscription_for_group(self):
        draft = WgDraftFactory(group__acronym='mars')
        RoleFactory(group__acronym='mars',name_id='chair',person=PersonFactory(user__username='marschairman'))

        url = urlreverse(ietf.community.views.subscription, kwargs={ "acronym": draft.group.acronym })

        setup_default_community_list_for_group(draft.group)

        login_testing_unauthorized(self, "marschairman", url)

        # test GET, rest is tested with personal list
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        
    def test_notification(self):
        PersonFactory(user__username='plain')
        draft = WgDraftFactory()

        clist = CommunityList.objects.create(user=User.objects.get(username="plain"))
        if not draft in clist.added_docs.all():
            clist.added_docs.add(draft)

        EmailSubscription.objects.create(community_list=clist, email=Email.objects.filter(person__user__username="plain").first(), notify_on="significant")

        mailbox_before = len(outbox)
        active_state = State.objects.get(type="draft", slug="active")
        system = Person.objects.get(name="(System)")
        add_state_change_event(draft, system, None, active_state)
        self.assertEqual(len(outbox), mailbox_before)

        mailbox_before = len(outbox)
        rfc_state = State.objects.get(type="draft", slug="rfc")
        add_state_change_event(draft, system, active_state, rfc_state)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue(draft.name in outbox[-1]["Subject"])
        
        
