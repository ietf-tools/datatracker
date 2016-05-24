from django.contrib.sites.models import Site

from ietf.group.models import Group, Role
from ietf.doc.models import DocEvent
from ietf.ietfauth.utils import has_role, is_authorized_in_doc_stream
from ietf.review.models import ReviewRequestStateName
from ietf.utils.mail import send_mail

def active_review_teams():
    # if there's a ReviewResultName defined, it's a review team
    return Group.objects.filter(state="active").exclude(reviewresultname=None)

def can_request_review_of_doc(user, doc):
    if not user.is_authenticated():
        return False

    return is_authorized_in_doc_stream(user, doc)

def can_manage_review_requests_for_team(user, team):
    if not user.is_authenticated():
        return False

    return Role.objects.filter(name__in=["secretary", "delegate"], person__user=user, group=team).exists() or has_role(user, "Secretariat")

def email_about_review_request(request, review_req, subject, msg, by, notify_secretary, notify_reviewer):
    """Notify possibly both secretary and reviewer about change, skipping
    a party if the change was done by that party."""

    def extract_email_addresses(roles):
        if any(r.person == by for r in roles if r):
            return []
        else:
            return [r.formatted_email() for r in roles if r]

    to = []

    if notify_secretary:
        to += extract_email_addresses(Role.objects.filter(name__in=["secretary", "delegate"], group=review_req.team).distinct())
    if notify_reviewer:
        to += extract_email_addresses([review_req.reviewer])

    if not to:
        return

    send_mail(request, list(set(to)), None, subject, "doc/mail/review_request_changed.txt", {
        "domain": Site.objects.get_current().domain,
        "review_req": review_req,
        "msg": msg,
    })


def assign_review_request_to_reviewer(request, review_req, reviewer):
    assert review_req.state_id in ("requested", "accepted")

    if reviewer == review_req.reviewer:
        return

    if review_req.reviewer:
        email_about_review_request(
            request, review_req,
            "Unassigned from review of %s" % review_req.doc.name,
            "%s has cancelled your assignment to the review." % request.user.person,
            by=request.user.person, notify_secretary=False, notify_reviewer=True)

    review_req.state = ReviewRequestStateName.objects.get(slug="requested")
    review_req.reviewer = reviewer
    review_req.save()

    DocEvent.objects.create(
        type="changed_review_request",
        doc=review_req.doc,
        by=request.user.person,
        desc="Request for {} review by {} is assigned to {}".format(
            review_req.type.name,
            review_req.team.acronym.upper(),
            review_req.reviewer.person if review_req.reviewer else "(None)",
        ),
    )

    email_about_review_request(
        request, review_req,
        "Assigned to review of %s" % review_req.doc.name,
        "%s has assigned you to review the document." % request.user.person,
        by=request.user.person, notify_secretary=False, notify_reviewer=True)
