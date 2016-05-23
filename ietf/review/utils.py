from ietf.group.models import Group, Role
from ietf.doc.models import DocEvent
from ietf.ietfauth.utils import has_role, is_authorized_in_doc_stream
from ietf.review.models import ReviewRequestStateName

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

    return Role.objects.filter(name="secretary", person__user=user, group=team).exists() or has_role(user, "Secretariat")

def assign_review_request_to_reviewer(review_req, reviewer, by):
    assert review_req.state_id in ("requested", "accepted")

    if review_req.reviewer == reviewer:
        return

    prev_state = review_req.state
    prev_reviewer = review_req.reviewer

    review_req.state = ReviewRequestStateName.objects.get(slug="requested")
    review_req.reviewer = reviewer
    review_req.save()

    DocEvent.objects.create(
        type="changed_review_request",
        doc=review_req.doc,
        by=by,
        desc="Request for {} review by {} is assigned to {}".format(
            review_req.type.name,
            review_req.team.acronym.upper(),
            review_req.reviewer.person if review_req.reviewer else "(None)",
        ),
    )
    
    if prev_state.slug != "requested" and prev_reviewer:
        # FIXME: email old reviewer?
        pass
