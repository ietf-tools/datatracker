# Copyright The IETF Trust 2023-2024, All Rights Reserved

import csv
from typing import List, Set, Tuple
from django.db.models import QuerySet

from email.utils import parseaddr

from ietf.person.models import Person
from ietf.submit.models import Submission


def authors_by_year(year: int) -> Set[str]:
    """Email addresses provided by I-D authors for drafts that were submitted in the given year."""
    addresses = set()
    for submission in Submission.objects.filter(
        submission_date__year=year, state="posted"
    ):
        addresses.update([a["email"] for a in submission.authors])
    return addresses


def submitters_by_year(year: int) -> Set[str]:
    """Email addresses provided by I-D submitters for drafts that were submitted in the given year."""
    return set(
        [
            parseaddr(a)[1]
            for a in Submission.objects.filter(
                submitter__contains="@", submission_date__year=year, state="posted"
            ).values_list("submitter", flat=True)
        ]
    )


def unique_people(addresses: List[str]) -> Tuple["QuerySet[Person]", Set]:
    """Identify Person records matching email addresses and email addresses with no Person record.

    Given a list of email addresses, return
    (
        a list of unique Person records with a matching email address,
        a list of unique email addresses with no matching Person record
    )
    The sum of the lengths of these lists is a best-approximation for how
    many unique people the list of addresses belong to.
    """
    persons = Person.objects.filter(email__address__in=addresses).distinct()
    known_email = set(persons.values_list("email__address", flat=True))
    return (persons, set(addresses) - set(known_email))


def write_reports(year: int) -> None:
    authors = authors_by_year(year)
    submitters = submitters_by_year(year)
    print(f"authors: {len(authors)}")
    print(f"submitters: {len(submitters)}")
    persons, nopersons = unique_people(authors)
    print(f"authors: unique persons: {len(persons)}, no person found: {len(nopersons)}")
    persons, nopersons = unique_people(submitters)
    print(
        f"submitters: unique persons: {len(persons)}, no person found: {len(nopersons)}"
    )
    with open("authors.csv", "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(authors)
    with open("submitters.csv", "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(submitters)
