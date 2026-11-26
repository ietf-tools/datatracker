# Copyright The IETF Trust 2026, All Rights Reserved
"""Values given to the templates that belong to a review team.

The chairs of a review team can edit these templates. A template is given
the values defined here and nothing else. The field names are the names the
templates used when they were given model objects, so that a template reads
{{ assignment.review_request.doc.name }} as before.

To make another value available, add a field to a class below and fill it
in the function that builds that class.
"""

import dataclasses
import datetime
import re

from ietf.dbtemplate.template import TemplateValues


@dataclasses.dataclass(frozen=True)
class NameValues(TemplateValues):
    slug: str
    name: str

    def __str__(self):
        return self.name


@dataclasses.dataclass(frozen=True)
class GroupValues(TemplateValues):
    acronym: str
    name: str

    def __str__(self):
        return self.name


@dataclasses.dataclass(frozen=True)
class PersonValues(TemplateValues):
    name: str
    plain_name: str
    ascii: str

    def __str__(self):
        return self.plain_name


@dataclasses.dataclass(frozen=True)
class ReviewerValues(TemplateValues):
    address: str
    person: PersonValues | None

    def __str__(self):
        return self.address


@dataclasses.dataclass(frozen=True)
class LastCallValues(TemplateValues):
    expires: datetime.datetime | None


@dataclasses.dataclass(frozen=True)
class DocumentValues(TemplateValues):
    name: str
    rev: str
    title: str
    telechat_date: datetime.date | None
    most_recent_ietflc: LastCallValues | None

    def __str__(self):
        return self.name


@dataclasses.dataclass(frozen=True)
class ReviewRequestValues(TemplateValues):
    doc: DocumentValues
    type: NameValues
    deadline: datetime.date
    requested_rev: str


@dataclasses.dataclass(frozen=True)
class AssignmentValues(TemplateValues):
    reviewer: ReviewerValues
    review_request: ReviewRequestValues
    state: NameValues
    result: NameValues | None
    assigned_on: datetime.datetime | None
    completed_on: datetime.datetime | None
    reviewed_rev: str


@dataclasses.dataclass(frozen=True)
class OpenAssignmentValues(AssignmentValues):
    section: str
    lastcall_ends: str | None
    earlier_review: bool
    earlier_reviews: str


@dataclasses.dataclass(frozen=True)
class ReviewAssignedValues(TemplateValues):
    """For /group/<team>/email/review_assigned.txt"""

    assigner: PersonValues
    reviewer: ReviewerValues
    prev_team_reviews: list[AssignmentValues]


@dataclasses.dataclass(frozen=True)
class OpenAssignmentsValues(TemplateValues):
    """For /group/<team>/email/open_assignments.txt"""

    group: GroupValues
    review_assignments: list[OpenAssignmentValues]
    rotation_list: list[PersonValues]


@dataclasses.dataclass(frozen=True)
class ReviewContentValues(TemplateValues):
    """For /group/<team>/review/content_templates/<review type>.txt"""

    assignment: AssignmentValues
    today: datetime.date


VALUES_CLASS_FOR_PATH = (
    (re.compile(r"^/group/[^/]+/email/review_assigned\.txt$"), ReviewAssignedValues),
    (re.compile(r"^/group/[^/]+/email/open_assignments\.txt$"), OpenAssignmentsValues),
    (re.compile(r"^/group/[^/]+/review/content_templates/[^/]+\.txt$"), ReviewContentValues),
)


def values_class_for_path(path):
    """Return the class of values that the template at path is given, or None."""
    for pattern, values_class in VALUES_CLASS_FOR_PATH:
        if pattern.match(path):
            return values_class
    return None


def name_values(name):
    return NameValues(slug=name.slug, name=name.name)


def group_values(group):
    return GroupValues(acronym=group.acronym, name=group.name)


def person_values(person):
    return PersonValues(
        name=person.name,
        plain_name=person.plain_name(),
        ascii=person.ascii,
    )


def reviewer_values(email):
    return ReviewerValues(
        address=email.address,
        person=person_values(email.person) if email.person else None,
    )


def document_values(doc):
    """This runs two queries, for the telechat date and the last call."""
    last_call = doc.most_recent_ietflc()
    return DocumentValues(
        name=doc.name,
        rev=doc.rev,
        title=doc.title,
        telechat_date=doc.telechat_date(),
        most_recent_ietflc=LastCallValues(expires=last_call.expires) if last_call else None,
    )


def _assignment_fields(assignment, doc):
    review_req = assignment.review_request
    return dict(
        reviewer=reviewer_values(assignment.reviewer),
        review_request=ReviewRequestValues(
            doc=doc or document_values(review_req.doc),
            type=name_values(review_req.type),
            deadline=review_req.deadline,
            requested_rev=review_req.requested_rev,
        ),
        state=name_values(assignment.state),
        result=name_values(assignment.result) if assignment.result else None,
        assigned_on=assignment.assigned_on,
        completed_on=assignment.completed_on,
        reviewed_rev=assignment.reviewed_rev,
    )


def assignment_values(assignment, doc=None):
    """doc is the DocumentValues for the reviewed document, if the caller has it."""
    return AssignmentValues(**_assignment_fields(assignment, doc))


def open_assignment_values(assignment, doc):
    """For an assignment that email_open_review_assignments() has annotated."""
    return OpenAssignmentValues(
        section=assignment.section,
        lastcall_ends=assignment.lastcall_ends,
        earlier_review=bool(assignment.earlier_review),
        earlier_reviews=getattr(assignment, "earlier_reviews", ""),
        **_assignment_fields(assignment, doc),
    )
