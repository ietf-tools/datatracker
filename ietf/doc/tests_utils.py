# Copyright The IETF Trust 2020, All Rights Reserved
import datetime

from ietf.group.factories import GroupFactory, RoleFactory
from ietf.name.models import DocTagName
from ietf.person.factories import PersonFactory
from ietf.utils.test_utils import TestCase
from ietf.person.models import Person
from ietf.doc.factories import DocumentFactory
from ietf.doc.models import State, DocumentActionHolder
from ietf.doc.utils import update_action_holders, add_state_change_event


class ActionHoldersTests(TestCase):

    def setUp(self):
        """Set up helper for the update_action_holders tests"""
        self.authors = PersonFactory.create_batch(3)
        self.ad = Person.objects.get(user__username='ad')
        self.group = GroupFactory()
        RoleFactory(name_id='ad', group=self.group, person=self.ad)
        
    def doc_in_iesg_state(self, slug):
        return DocumentFactory(authors=self.authors, group=self.group, ad=self.ad, states=[('draft-iesg', slug)])

    def update_doc_state(self, doc, new_state, add_tags=None, remove_tags=None):
        """Update document state/tags, create change event, and save"""
        prev_tags = list(doc.tags.all())  # list to make sure we retrieve now
        # prev_action_holders = list(doc.action_holders.all())

        prev_state = doc.get_state(new_state.type_id)
        if new_state != prev_state:
            doc.set_state(new_state)

        if add_tags:
            doc.tags.add(*DocTagName.objects.filter(slug__in=add_tags))
        if remove_tags:
            doc.tags.remove(*DocTagName.objects.filter(slug__in=remove_tags))
        new_tags = list(doc.tags.all())

        events = []
        e = add_state_change_event(
            doc,
            Person.objects.get(name='(System)'),
            prev_state, new_state,
            prev_tags, new_tags)
        self.assertIsNotNone(e, 'Test logic error')
        events.append(e)
        e = update_action_holders(doc, prev_state, new_state, prev_tags, new_tags)
        if e:
            events.append(e)
        doc.save_with_history(events)


    def test_update_action_holders_by_state(self):
        """Doc action holders should auto-update correctly on state change"""
        # Test the transition from every state to each of its 'next_states'

        for initial_state in State.objects.filter(type__slug='draft-iesg'):
            for next_state in initial_state.next_states.all():
                # Test with no action holders initially
                doc = DocumentFactory(
                    authors=self.authors,
                    group=self.group,
                    ad=self.ad,
                    states=[('draft-iesg', initial_state.slug)],
                )
                docevents_before = set(doc.docevent_set.all())

                self.update_doc_state(doc, next_state)

                new_docevents = set(doc.docevent_set.all()).difference(docevents_before)
                self.assertIn(doc.latest_event(type='changed_state'), new_docevents)

                if next_state.slug in DocumentActionHolder.CLEAR_ACTION_HOLDERS_STATES:
                    self.assertCountEqual(doc.action_holders.all(), [])
                    self.assertEqual(len(new_docevents), 1)
                else:
                    self.assertCountEqual(
                        doc.action_holders.all(), [doc.ad],
                        'AD should be only action holder after transition to %s' % next_state.slug)

                    self.assertEqual(len(new_docevents), 2)
                    change_event = doc.latest_event(type='changed_action_holders')
                    self.assertIn(change_event, new_docevents)
                    self.assertIn('Changed action holders', change_event.desc)
                    self.assertIn(doc.ad.name, change_event.desc)
                doc.delete()  # clean up for next iteration

                # Test with action holders initially
                doc = DocumentFactory(
                    authors=self.authors,
                    group=self.group,
                    ad=self.ad,
                    states=[('draft-iesg', initial_state.slug)],
                )
                doc.action_holders.add(*self.authors)  # adds all authors
                docevents_before = set(doc.docevent_set.all())

                self.update_doc_state(doc, next_state)

                new_docevents = set(doc.docevent_set.all()).difference(docevents_before)
                self.assertEqual(len(new_docevents), 2)
                self.assertIn(doc.latest_event(type='changed_state'), new_docevents)
                change_event = doc.latest_event(type='changed_action_holders')
                self.assertIn(change_event, new_docevents)

                if next_state.slug in DocumentActionHolder.CLEAR_ACTION_HOLDERS_STATES:
                    self.assertCountEqual(doc.action_holders.all(), [])
                    self.assertIn('Removed all action holders', change_event.desc)
                else:
                    self.assertCountEqual(
                        doc.action_holders.all(), [doc.ad],
                        'AD should be only action holder after transition to %s' % next_state.slug)
                    self.assertIn('Changed action holders', change_event.desc)
                    self.assertIn(doc.ad.name, change_event.desc)
                doc.delete()  # clean up for next iteration

    def test_update_action_holders_with_no_ad(self):
        """A document with no AD should be handled gracefully"""
        doc = self.doc_in_iesg_state('idexists')
        doc.ad = None
        doc.save()
        
        docevents_before = set(doc.docevent_set.all())
        self.update_doc_state(doc, State.objects.get(slug='pub-req'))
        new_docevents = set(doc.docevent_set.all()).difference(docevents_before)
        self.assertEqual(len(new_docevents), 1)
        self.assertIn(doc.latest_event(type='changed_state'), new_docevents)
        self.assertCountEqual(doc.action_holders.all(), [])

    def test_update_action_holders_resets_age(self):
        """Action holder age should reset when document state changes"""
        doc = self.doc_in_iesg_state('pub-req')
        doc.action_holders.set([self.ad])
        dah = doc.documentactionholder_set.get(person=self.ad)
        dah.time_added = datetime.datetime(2020, 1, 1)  # arbitrary date in the past
        dah.save()

        self.assertNotEqual(doc.documentactionholder_set.get(person=self.ad).time_added.date(), datetime.date.today())
        self.update_doc_state(doc, State.objects.get(slug='ad-eval'))
        self.assertEqual(doc.documentactionholder_set.get(person=self.ad).time_added.date(), datetime.date.today())

    def test_update_action_holders_add_tag_need_rev(self):
        """Adding need-rev tag adds authors as action holders"""
        doc = self.doc_in_iesg_state('pub-req')
        first_author = self.authors[0]
        doc.action_holders.add(first_author)
        self.assertCountEqual(doc.action_holders.all(), [first_author])
        self.update_doc_state(doc,
                              doc.get_state('draft-iesg'),
                              add_tags=['need-rev'],
                              remove_tags=None)
        self.assertCountEqual(doc.action_holders.all(), self.authors)

    def test_update_action_holders_add_tag_need_rev_no_dups(self):
        """Adding need-rev tag does not duplicate existing action holders"""
        doc = self.doc_in_iesg_state('pub-req')
        self.assertCountEqual(doc.action_holders.all(), [])
        self.update_doc_state(doc,
                              doc.get_state('draft-iesg'),
                              add_tags=['need-rev'],
                              remove_tags=None)
        self.assertCountEqual(doc.action_holders.all(), self.authors)

    def test_update_action_holders_remove_tag_need_rev(self):
        """Removing need-rev tag drops authors as action holders"""
        doc = self.doc_in_iesg_state('pub-req')
        doc.tags.add(DocTagName.objects.get(slug='need-rev'))
        self.assertEqual(doc.action_holders.count(), 0)
        self.update_doc_state(doc,
                              doc.get_state('draft-iesg'),
                              add_tags=None,
                              remove_tags=['need-rev'])
        self.assertEqual(doc.action_holders.count(), 0)

    def test_update_action_holders_add_tag_need_rev_ignores_non_authors(self):
        """Adding need-rev tag does not affect existing action holders"""
        doc = self.doc_in_iesg_state('pub-req')
        doc.action_holders.add(self.ad)
        self.assertCountEqual(doc.action_holders.all(),[self.ad])
        self.update_doc_state(doc,
                              doc.get_state('draft-iesg'),
                              add_tags=['need-rev'],
                              remove_tags=None)
        self.assertCountEqual(doc.action_holders.all(), [self.ad] + self.authors)

    def test_update_action_holders_remove_tag_need_rev_ignores_non_authors(self):
        """Removing need-rev tag does not affect non-author action holders"""
        doc = self.doc_in_iesg_state('pub-req')
        doc.tags.add(DocTagName.objects.get(slug='need-rev'))
        doc.action_holders.add(self.ad)
        self.assertCountEqual(doc.action_holders.all(), [self.ad])
        self.update_doc_state(doc,
                              doc.get_state('draft-iesg'),
                              add_tags=None,
                              remove_tags=['need-rev'])
        self.assertCountEqual(doc.action_holders.all(), [self.ad])

    def test_doc_action_holders_enabled(self):
        """Action holders should only be enabled in certain states"""
        doc = self.doc_in_iesg_state('idexists')
        self.assertFalse(doc.action_holders_enabled())

        for state in State.objects.filter(type='draft-iesg').exclude(slug='idexists'):
            doc.set_state(state)
            self.assertTrue(doc.action_holders_enabled())