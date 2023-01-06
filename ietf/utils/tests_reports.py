# Copyright The IETF Trust 2023, All Rights Reserved

import datetime

import debug  # pyflakes:ignore

from ietf.doc.factories import IndividualDraftFactory
from ietf.person.factories import EmailFactory
from ietf.person.models import Person, Email
from ietf.submit.factories import SubmissionFactory
from ietf.utils.reports import authors_by_year, submitters_by_year, unique_people
from ietf.utils.test_utils import TestCase


class ReportTests(TestCase):
    def setUp(self):
        super().setUp()

        # Build 5 drafts submitted across two years, with 6 unique authors,
        # one of which has more than one email address (author0@example.com and
        # author0@example.net). The drafts are submitted by two of the six authors,
        # again using multiple addresses for author0, and two identities that are not authors.
        # Then build a draft where the submission's submitter info doesn't contain an email
        # address (we have those in the production database) to make sure that submitter isn't
        # counted.

        self.make_draft_submission(
            year=2020,
            month=1,
            day=1,
            submitter_name="Author 0",
            submitter_email="author0@example.net",
            author_nameaddrs=[
                ("Author 0", "author0@example.net"),
                ("Author 1", "author1@example.net"),
            ],
        )

        self.make_draft_submission(
            year=2020,
            month=3,
            day=3,
            submitter_name="NotanAuthor 0",
            submitter_email="notanauthor0@example.net",
            author_nameaddrs=[
                ("Author 0", "author0@example.com"),  # Note alternate email
                ("Author 3", "author3@example.net"),
            ],
        )

        self.make_draft_submission(
            year=2020,
            month=12,
            day=31,
            submitter_name="Author 3",
            submitter_email="author3@example.net",
            author_nameaddrs=[("Author 3", "author3@example.net")],
        )

        self.make_draft_submission(
            year=2021,
            month=1,
            day=1,
            submitter_name="Author 0",
            submitter_email="author0@example.com",  # Note alternate email
            author_nameaddrs=[
                ("Author 0", "author0@example.com"),
                ("Author 4", "author4@example.net"),
            ],
        )

        self.make_draft_submission(
            year=2021,
            month=12,
            day=31,
            submitter_name="NoatanAuthor 2",
            submitter_email="notanauthor2@example.net",
            author_nameaddrs=[
                ("Author 0", "author0@example.net"),
                ("Author 3", "author3@example.net"),
                ("Author 5", "author5@example.net"),
            ],
        )

        self.make_draft_submission(
            year=2021,
            month=12,
            day=31,
            submitter_name="Trouble Maker",
            submitter_email="",
            author_nameaddrs=[("Author 0", "author0@example.net")],
        )

    def make_draft_submission(
        self, year, month, day, submitter_name, submitter_email, author_nameaddrs
    ):

        authors = []
        for name, addr in author_nameaddrs:
            person = Person.objects.filter(name=name).first()
            if not person:
                person = EmailFactory(person__name=name, address=addr).person
            elif not Email.objects.filter(address=addr).exists():
                EmailFactory(person=person, address=addr)
            authors.append(person)

        submission = SubmissionFactory(
            submission_date=datetime.date(year, month, day),
            submitter_name=submitter_name,
            submitter_email=submitter_email,
            state_id="posted",
        )
        submission.authors = [
            {
                "name": f"{name}",
                "email": f"{addr}",
                "affiliation": "",
                "country": "",
                "errors": [],
            }
            for name, addr in author_nameaddrs
        ]

        submission.save()
        IndividualDraftFactory(submission=submission, authors=authors)

    def test_authors_by_year(self):
        authors2020 = authors_by_year(2020)
        self.assertEqual(
            set(authors2020),
            set(
                [
                    "author0@example.net",
                    "author0@example.com",
                    "author1@example.net",
                    "author3@example.net",
                ]
            ),
        )
        authors2021 = authors_by_year(2021)
        self.assertEqual(
            set(authors2021),
            set(
                [
                    "author0@example.net",
                    "author0@example.com",
                    "author3@example.net",
                    "author4@example.net",
                    "author5@example.net",
                ]
            ),
        )

    def test_submitters_by_year(self):
        sub2020 = submitters_by_year(2020)
        self.assertEqual(
            set(sub2020),
            set(
                [
                    "author0@example.net",
                    "author3@example.net",
                    "notanauthor0@example.net",
                ]
            ),
        )
        sub2021 = submitters_by_year(2021)
        self.assertEqual(
            set(sub2021), set(["author0@example.com", "notanauthor2@example.net"])
        )

    def test_unique_people(self):
        persons, addrs = unique_people(
            [
                "notanauthor0@example.com",
                "author0@example.net",
                "author0@example.com",
                "author1@example.net",
                "notanauthor0@example.com",
            ]
        )
        self.assertEqual(addrs, ["notanauthor0@example.com"])
        self.assertEqual(
            set(persons), set(Person.objects.filter(name__in=("Author 0", "Author 1")))
        )
        self.assertEqual(len(persons) + len(addrs), 3)
