# Copyright The IETF Trust 2020, All Rights Reserved
import datetime
import debug  # pyflakes:ignore

from pathlib import Path
from unittest.mock import call, patch

from django.conf import settings
from django.db import IntegrityError
from django.test.utils import override_settings
from django.utils import timezone

from ietf.group.factories import GroupFactory, RoleFactory
from ietf.name.models import DocTagName
from ietf.person.factories import PersonFactory
from ietf.utils.test_utils import TestCase, name_of_file_containing, reload_db_objects
from ietf.person.models import Person
from ietf.doc.factories import DocumentFactory, WgRfcFactory, WgDraftFactory
from ietf.doc.models import State, DocumentActionHolder, DocumentAuthor
from ietf.doc.utils import (update_action_holders, add_state_change_event, update_documentauthors,
                            fuzzy_find_documents, rebuild_reference_relations, build_file_urls,
                            ensure_draft_bibxml_path_exists, update_or_create_draft_bibxml_file)
from ietf.utils.draft import Draft, PlaintextDraft
from ietf.utils.xmldraft import XMLDraft


class ActionHoldersTests(TestCase):

    def setUp(self):
        """Set up helper for the update_action_holders tests"""
        super().setUp()
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
        dah.time_added = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)  # arbitrary date in the past
        dah.save()

        right_now = timezone.now()
        self.assertLess(doc.documentactionholder_set.get(person=self.ad).time_added, right_now)
        self.update_doc_state(doc, State.objects.get(slug='ad-eval'))
        self.assertGreaterEqual(doc.documentactionholder_set.get(person=self.ad).time_added, right_now)

    def test_update_action_holders_add_tag_need_rev(self):
        """Adding need-rev tag drops AD and adds authors as action holders"""
        doc = self.doc_in_iesg_state('pub-req')
        first_author = self.authors[0]
        doc.action_holders.add(first_author)
        doc.action_holders.add(doc.ad)
        self.assertCountEqual(doc.action_holders.all(), [first_author, doc.ad])
        self.update_doc_state(doc,
                              doc.get_state('draft-iesg'),
                              add_tags=['need-rev'],
                              remove_tags=None)
        self.assertCountEqual(doc.action_holders.all(), self.authors)
        self.assertNotIn(self.ad, doc.action_holders.all())
        
        # Check case where an author is ad
        doc = self.doc_in_iesg_state('pub-req')
        doc.ad = first_author
        doc.save()
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

    def test_update_action_holders_add_tag_ad_f_up(self):
        doc = self.doc_in_iesg_state('pub-req')
        self.assertEqual(doc.action_holders.count(), 0)
        self.update_doc_state(doc, doc.get_state('draft-iesg'), add_tags=['ad-f-up'])
        self.assertCountEqual(doc.action_holders.all(), [self.ad])

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
        other_person = PersonFactory()
        doc.action_holders.add(other_person)
        self.assertCountEqual(doc.action_holders.all(),[other_person])
        self.update_doc_state(doc,
                              doc.get_state('draft-iesg'),
                              add_tags=['need-rev'],
                              remove_tags=None)
        self.assertCountEqual(doc.action_holders.all(), [other_person] + self.authors)

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


class MiscTests(TestCase):
    def test_update_documentauthors_with_nulls(self):
        """A 'None' value in the affiliation/country should be handled correctly"""
        author_person = PersonFactory()
        doc = DocumentFactory(authors=[author_person])
        doc.documentauthor_set.update(
            affiliation='Some Affiliation', country='USA'
        )
        try:
            events = update_documentauthors(
                doc,
                [
                    DocumentAuthor(
                        person=author_person,
                        email=author_person.email(),
                        affiliation=None,
                        country=None,
                    )
                ],
            )
        except IntegrityError as err:
            self.fail('IntegrityError was raised: {}'.format(err))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, 'edited_authors')
        self.assertIn('cleared affiliation (was "Some Affiliation")', events[0].desc)
        self.assertIn('cleared country (was "USA")', events[0].desc)
        docauth = doc.documentauthor_set.first()
        self.assertEqual(docauth.affiliation, '')
        self.assertEqual(docauth.country, '')

    def do_fuzzy_find_documents_rfc_test(self, name):
        draft = WgDraftFactory(name=name, create_revisions=(0, 1, 2))
        rfc = WgRfcFactory()
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
        draft, rfc = reload_db_objects(draft, rfc)

        # by canonical name
        found = fuzzy_find_documents(rfc.name, None)
        self.assertCountEqual(found.documents, [rfc])
        self.assertEqual(found.matched_rev, None)
        self.assertEqual(found.matched_name, rfc.name)

        # by draft name, no rev
        found = fuzzy_find_documents(draft.name, None)
        self.assertCountEqual(found.documents, [draft])
        self.assertEqual(found.matched_rev, None)
        self.assertEqual(found.matched_name, draft.name)

        # by draft name, latest rev
        found = fuzzy_find_documents(draft.name, '02')
        self.assertCountEqual(found.documents, [draft])
        self.assertEqual(found.matched_rev, '02')
        self.assertEqual(found.matched_name, draft.name)

        # by draft name, earlier rev
        found = fuzzy_find_documents(draft.name, '01')
        self.assertCountEqual(found.documents, [draft])
        self.assertEqual(found.matched_rev, '01')
        self.assertEqual(found.matched_name, draft.name)

        # wrong name or revision
        found = fuzzy_find_documents(draft.name + '-incorrect')
        self.assertCountEqual(found.documents, [], 'Should not find document that does not match')
        found = fuzzy_find_documents(draft.name + '-incorrect', '02')
        self.assertCountEqual(found.documents, [], 'Still should not find document, even with a version')
        found = fuzzy_find_documents(draft.name, '22')
        self.assertCountEqual(found.documents, [draft],
                              'Should find document even if rev does not exist')
        
        # by rfc name mistakenly trying to provide a revision
        found = fuzzy_find_documents(rfc.name+"-22")
        self.assertCountEqual(found.documents, [rfc], "Should ignore versions when fuzzyfinding RFCs" )
        found = fuzzy_find_documents(rfc.name,"22")
        self.assertCountEqual(found.documents, [rfc], "Should ignore versions when fuzzyfinding RFCs" )


    def test_fuzzy_find_documents(self):
        # Should add additional tests/test cases for other document types/name formats
        self.do_fuzzy_find_documents_rfc_test('draft-normal-name')
        self.do_fuzzy_find_documents_rfc_test('draft-name-with-number-01')
        self.do_fuzzy_find_documents_rfc_test('draft-name-that-has-two-02-04')
        self.do_fuzzy_find_documents_rfc_test('draft-wild-01-numbers-0312')

    @override_settings(RFC_FILE_TYPES=['pdf'], IDSUBMIT_FILE_TYPES=['xml'])
    @patch('ietf.doc.utils.os.path.exists', return_value=True)
    def test_build_file_urls(self, mocked):
        # a cursory test only - does not check details of how URLs are constructed
        self.assertEqual(
            build_file_urls(DocumentFactory(type_id='statchg')), ([], []),
            'Non-draft Document should return empty sets'
        )

        with self.assertRaises(AssertionError):
            build_file_urls(WgDraftFactory(rev=''))

        urls, types = build_file_urls(WgDraftFactory(rev='23'))
        self.assertEqual(['xml', 'bibtex', 'bibxml'], [t for t, _ in urls])
        self.assertEqual(types, ['xml'])

        urls, types = build_file_urls(WgRfcFactory(rev=''))
        self.assertEqual(['pdf', 'bibtex'], [t for t, _ in urls])
        self.assertEqual(types, ['pdf'])

        urls, types = build_file_urls(WgRfcFactory(rev='23'))
        self.assertEqual(['pdf', 'bibtex'], [t for t, _ in urls])
        self.assertEqual(types, ['pdf'])


class RebuildReferenceRelationsTests(TestCase):
    def setUp(self):
        super().setUp()
        self.doc = WgDraftFactory()  # document under test
        # Other documents that should be found by rebuild_reference_relations
        self.normative, self.informative, self.unknown = WgRfcFactory.create_batch(3) # AMHERE - these need to have rfc names.
        for relationship in ['refnorm', 'refinfo', 'refunk', 'refold']:
            self.doc.relateddocument_set.create(
                target=WgRfcFactory(),
                relationship_id=relationship,
            )
        self.updated = WgRfcFactory()  # related document that should be left alone
        self.doc.relateddocument_set.create(target=self.updated, relationship_id='updates')
        self.assertCountEqual(self.doc.relateddocument_set.values_list('relationship__slug', flat=True),
                              ['refnorm', 'refinfo', 'refold', 'refunk', 'updates'],
                              'Test conditions set up incorrectly: wrong prior document relationships')
        for other_doc in [self.normative, self.informative, self.unknown]:
            self.assertEqual(
                self.doc.relateddocument_set.filter(target__name=other_doc.name).count(),
                0,
                'Test conditions set up incorrectly: new documents already related',
            )

    def _get_refs_return_value(self):
        return {
            self.normative.name: Draft.REF_TYPE_NORMATIVE,
            self.informative.name: Draft.REF_TYPE_INFORMATIVE,
            self.unknown.name: Draft.REF_TYPE_UNKNOWN,
            'draft-not-found': Draft.REF_TYPE_NORMATIVE,
        }

    def test_requires_txt_or_xml(self):
        result = rebuild_reference_relations(self.doc, {})
        self.assertCountEqual(result.keys(), ['errors'])
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('No Internet-Draft text available', result['errors'][0],
                      'Error should be reported if no Internet-Draft file is given')

        result = rebuild_reference_relations(self.doc, {'md': 'cant-do-this.md'})
        self.assertCountEqual(result.keys(), ['errors'])
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('No Internet-Draft text available', result['errors'][0],
                      'Error should be reported if no XML or plaintext file is given')

    @patch.object(XMLDraft, 'get_refs')
    @patch.object(XMLDraft, '__init__', return_value=None)
    def test_xml(self, mock_init, mock_get_refs):
        """Should build reference relations with only XML"""
        mock_get_refs.return_value = self._get_refs_return_value()

        result = rebuild_reference_relations(self.doc, {'xml': 'file.xml'})

        # if the method of calling the XMLDraft() constructor changes, this will need to be updated
        xmldraft_init_args, _ = mock_init.call_args
        self.assertEqual(xmldraft_init_args, ('file.xml',), 'XMLDraft initialized with unexpected arguments')
        self.assertEqual(
            result,
            {
                'warnings': ['There were 1 references with no matching Document'],
                'unfound': ['draft-not-found'],
            }
        )

        self.assertCountEqual(
            self.doc.relateddocument_set.values_list('target__name', 'relationship__slug'),
            [
                (self.normative.name, 'refnorm'),
                (self.informative.name, 'refinfo'),
                (self.unknown.name, 'refunk'),
                (self.updated.name, 'updates'),
            ]
        )

    @patch.object(PlaintextDraft, 'get_refs')
    @patch.object(PlaintextDraft, '__init__', return_value=None)
    def test_plaintext(self, mock_init, mock_get_refs):
        """Should build reference relations with only plaintext"""
        mock_get_refs.return_value = self._get_refs_return_value()

        with name_of_file_containing('contents') as temp_file_name:
            result = rebuild_reference_relations(self.doc, {'txt': temp_file_name})

        # if the method of calling the PlaintextDraft() constructor changes, this test will need to be updated
        _, mock_init_kwargs = mock_init.call_args
        self.assertEqual(mock_init_kwargs, {'text': 'contents', 'source': temp_file_name},
                         'PlaintextDraft initialized with unexpected arguments')
        self.assertEqual(
            result,
            {
                'warnings': ['There were 1 references with no matching Document'],
                'unfound': ['draft-not-found'],
            }
        )

        self.assertCountEqual(
            self.doc.relateddocument_set.values_list('target__name', 'relationship__slug'),
            [
                (self.normative.name, 'refnorm'),
                (self.informative.name, 'refinfo'),
                (self.unknown.name, 'refunk'),
                (self.updated.name, 'updates'),
            ]
        )

    @patch.object(PlaintextDraft, '__init__')
    @patch.object(XMLDraft, 'get_refs')
    @patch.object(XMLDraft, '__init__', return_value=None)
    def test_xml_and_plaintext(self, mock_init, mock_get_refs, mock_plaintext_init):
        """Should build reference relations with XML when plaintext also available"""
        mock_get_refs.return_value = self._get_refs_return_value()

        result = rebuild_reference_relations(self.doc, {'txt': 'file.txt', 'xml': 'file.xml'})

        self.assertFalse(mock_plaintext_init.called, 'PlaintextDraft should not be used when XML is available')

        # if the method of calling the XMLDraft() constructor changes, this will need to be updated
        xmldraft_init_args, _ = mock_init.call_args
        self.assertEqual(xmldraft_init_args, ('file.xml',), 'XMLDraft initialized with unexpected arguments')
        self.assertEqual(
            result,
            {
                'warnings': ['There were 1 references with no matching Document'],
                'unfound': ['draft-not-found'],
            }
        )

        self.assertCountEqual(
            self.doc.relateddocument_set.values_list('target__name', 'relationship__slug'),
            [
                (self.normative.name, 'refnorm'),
                (self.informative.name, 'refinfo'),
                (self.unknown.name, 'refunk'),
                (self.updated.name, 'updates'),
            ]
        )


class DraftBibxmlTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ["BIBXML_BASE_PATH"]

    def test_ensure_draft_bibxml_path_exists(self):
        expected = Path(settings.BIBXML_BASE_PATH) / "bibxml-ids"
        self.assertFalse(expected.exists())
        ensure_draft_bibxml_path_exists()
        self.assertTrue(expected.is_dir())  # false if does not exist or is not dir

    @patch("ietf.doc.utils.bibxml_for_draft", return_value="This\ris\nmy\r\nbibxml")
    def test_create_draft_bibxml_file(self, mock):
        bibxml_path = Path(settings.BIBXML_BASE_PATH) / "bibxml-ids"
        bibxml_path.mkdir(exist_ok=False)  # expect to start with a clean slate
        
        doc = DocumentFactory()
        ref_path = bibxml_path / f"reference.I-D.{doc.name}-26.xml"  # we're pretending it's rev 26
        
        update_or_create_draft_bibxml_file(doc, "26")
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(mock.call_args, call(doc, "26"))
        self.assertEqual(ref_path.read_text(), "This\nis\nmy\nbibxml")

    @patch("ietf.doc.utils.bibxml_for_draft", return_value="This\ris\nmy\r\nbibxml")
    def test_update_draft_bibxml_file(self, mock):
        bibxml_path = Path(settings.BIBXML_BASE_PATH) / "bibxml-ids"
        bibxml_path.mkdir(exist_ok=False)  # expect to start with a clean slate
        
        doc = DocumentFactory()
        ref_path = bibxml_path / f"reference.I-D.{doc.name}-26.xml"  # we're pretending it's rev 26
        ref_path.write_text("Old data")

        # should replace it
        update_or_create_draft_bibxml_file(doc, "26")
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(mock.call_args, call(doc, "26"))
        self.assertEqual(ref_path.read_text(), "This\nis\nmy\nbibxml")

        # should leave it alone if it differs only by leading/trailing whitespace
        mock.reset_mock()
        mock.return_value = "   \n  This\nis\nmy\nbibxml  "
        update_or_create_draft_bibxml_file(doc, "26")
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(mock.call_args, call(doc, "26"))
        self.assertEqual(ref_path.read_text(), "This\nis\nmy\nbibxml")
