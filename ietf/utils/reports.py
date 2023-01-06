# Copyright The IETF Trust 2023, All Rights Reserved

from typing import List, Tuple

from email.utils import parseaddr

from ietf.person.models import Person
from ietf.submit.models import Submission


def authors_by_year(year: int) -> List[str]:
    """
    Returns the email addresses provided by I-D authors for
    drafts that were submitted in the given year.
    """
    addresses = set()
    for submission in Submission.objects.filter(submission_date__year=year):
        addresses.update([a["email"] for a in submission.authors])
    return list(addresses)


def submitters_by_year(year: int) -> List[str]:
    """
    Returns the email addresses provided by I-D submitters for
    drafts that were submitted in the given year.
    """
    return list(
        set(
            [
                parseaddr(a)[1]
                for a in Submission.objects.filter(
                    submitter__contains="@", submission_date__year=year
                ).values_list("submitter", flat=True)
            ]
        )
    )


def unique_people(addresses: List[str]) -> Tuple[List, List]:
    """
    Given a list of email addresses, return
    (
        a list of unique Person records with a matching email address,
        a list of unique email addresses with no matching Person record
    )
    The sum of the lenghts of these lists is a best-approximation for how
    many unique people the list of addresses belong to.
    """
    persons = Person.objects.filter(email__address__in=addresses).distinct()
    known_email = set(persons.values_list("email__address", flat=True))
    return (list(persons), list(set(addresses) - set(known_email)))
