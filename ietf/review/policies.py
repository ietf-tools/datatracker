# Copyright The IETF Trust 2019-2021, All Rights Reserved


import re

from django.db.models.aggregates import Max
from django.utils import timezone
from simple_history.utils import bulk_update_with_history

from ietf.doc.models import DocumentAuthor, DocAlias
from ietf.doc.utils import extract_complete_replaces_ancestor_mapping_for_docs
from ietf.group.models import Role
from ietf.person.models import Person
import debug                            # pyflakes:ignore
from ietf.review.models import NextReviewerInTeam, ReviewerSettings, ReviewWish, ReviewRequest, \
    ReviewAssignment, ReviewTeamSettings
from ietf.review.utils import (current_unavailable_periods_for_reviewers,
                               days_needed_to_fulfill_min_interval_for_reviewers, 
                               get_default_filter_re,
                               latest_review_assignments_for_reviewers)
from ietf.utils import log

"""
This file contains policies regarding reviewer queues.
The policies are documented in more detail on:
https://trac.ietf.org/trac/ietfdb/wiki/ReviewerQueuePolicy
Terminology used here should match terminology used in that document.
"""


def get_reviewer_queue_policy(team):
    try:
        settings = ReviewTeamSettings.objects.get(group=team)
    except ReviewTeamSettings.DoesNotExist:
        raise ValueError('Request for a reviewer queue policy for team {} '
                         'which has no ReviewTeamSettings'.format(team))
    try:
        policy = QUEUE_POLICY_NAME_MAPPING[settings.reviewer_queue_policy.slug]
    except KeyError:
        raise ValueError('Team {} has unknown reviewer queue policy: '
                         '{}'.format(team, settings.reviewer_queue_policy.slug))
    return policy(team)


def persons_with_previous_review(team, review_req, possible_person_ids, state_id):
    """ Collect anyone in possible_person_ids that have reviewed the document before
    
    Also considers ancestor documents. The possible_person_ids elements can be Person objects or PKs
    Returns a set of Person IDs.
    """
    doc_names = {review_req.doc.name}.union(*extract_complete_replaces_ancestor_mapping_for_docs([review_req.doc.name]).values())
    has_reviewed_previous = ReviewRequest.objects.filter(
        doc__name__in=doc_names,
        reviewassignment__reviewer__person__in=possible_person_ids,
        reviewassignment__state=state_id,
        team=team,
    ).distinct()
    if review_req.pk is not None:
        has_reviewed_previous = has_reviewed_previous.exclude(pk=review_req.pk)
    has_reviewed_previous = set(
        has_reviewed_previous.values_list("reviewassignment__reviewer__person", flat=True))
    return has_reviewed_previous


class AbstractReviewerQueuePolicy:
    def __init__(self, team):
        self.team = team
        
    def assign_reviewer(self, review_req, reviewer, add_skip):
        """Assign a reviewer to a request and update policy state accordingly"""
        # Update policy state first - needed by LRU policy to correctly compute whether assignment was in-order
        self.update_policy_state_for_assignment(review_req, reviewer.person, add_skip)
        return review_req.reviewassignment_set.create(state_id='assigned', reviewer=reviewer, assigned_on=timezone.now())

    def default_reviewer_rotation_list(self, include_unavailable=False):
        """ Return a list of reviewers (Person objects) in the default reviewer rotation for a policy.
        
        Subclasses should pretty much always override this. The default implementation provides the filtering
        behavior expected of queue policies.
        """
        # Default is just a filtered list of reviewers for the team, in arbitrary order.
        rotation_list = list(Person.objects.filter(role__name="reviewer", role__group=self.team))
        if not include_unavailable:
            rotation_list = self._filter_unavailable_reviewers(rotation_list)
        return rotation_list

    def return_reviewer_to_rotation_top(self, reviewer_person):
        """
        Return a reviewer to the top of the rotation, e.g. because they rejected a review,
        and should retroactively not have been rotated over.
        """
        raise NotImplementedError  # pragma: no cover
    
    def default_reviewer_rotation_list_without_skipped(self):
        """
        Return a list of reviewers (Person objects) in the default reviewer rotation for a policy,
        while skipping those with a skip_next>0.
        """
        return [r for r in self.default_reviewer_rotation_list() if not self._reviewer_settings_for(r).skip_next]

    def update_policy_state_for_assignment(self, review_req, assignee_person, add_skip=False):
        """Update the skip_count if the assignment was in order."""
        self._clear_request_next_assignment(assignee_person)

        rotation = self._filter_unavailable_reviewers(
            self.default_reviewer_rotation_list(include_unavailable=True),  # we are going to filter for ourselves
            review_req,
        )

        # Use PKs, not objects, to avoid bugs arising from object identity comparisons
        rotation_pks = [r.pk for r in rotation]
        if len(rotation_pks) == 0:
            return
        # assignee_person should be in the rotation list, otherwise they should not have been an option
        log.assertion('assignee_person.pk in rotation_pks')

        if self._assignment_in_order(rotation_pks, assignee_person):
            self._update_skip_next(rotation_pks, assignee_person)

        if add_skip:
            self._add_skip(assignee_person)

    def _update_skip_next(self, rotation_pks, assignee_person):
        """Decrement skip_next for all users skipped"""
        assignee_index = rotation_pks.index(assignee_person.pk)
        skipped = rotation_pks[0:assignee_index]
        skipped_settings = self.team.reviewersettings_set.filter(person__in=skipped)  # list of PKs is valid here
        for ss in skipped_settings:
            ss.skip_next = max(0, ss.skip_next - 1)  # ensure we don't go negative
        bulk_update_with_history(skipped_settings,
                                 ReviewerSettings,
                                 ['skip_next'],
                                 default_change_reason='skipped')

    def _assignment_in_order(self, rotation_pks, assignee_person):
        """Is this an in-order assignment?"""
        if assignee_person.pk not in rotation_pks:
            return False  # picking from off the list is not in order

        # map from person ID to skip_next
        skip_next = dict(
            self.team.reviewersettings_set.filter(
                person__in=rotation_pks
            ).values_list('person_id', 'skip_next')
        )
        rotation_skips = [skip_next.get(pk, 0) for pk in rotation_pks]
        min_skip = min(rotation_skips)  # usually 0, but not guaranteed
        assignee_index = rotation_pks.index(assignee_person.pk)
        assignee_skip = rotation_skips[assignee_index]
        
        # If the assignee should be skipped, the selection is not in order
        if assignee_skip != min_skip:
            return False
        
        # If any of the preceding reviewers should not have been skipped, the selection is not in order
        for earlier_skip in rotation_skips[0:assignee_index]: 
            if earlier_skip <= min_skip:
                return False

        # The selection was in order
        return True

    # TODO : Change this field to deal with multiple already assigned reviewers???
    def setup_reviewer_field(self, field, review_req):
        """
        Fill a choice field with the recommended assignment order of reviewers for a review request.
        The field should be an instance similar to
            PersonEmailChoiceField(label="Assign Reviewer", empty_label="(None)")
        """

        # Collect a set of person IDs for people who have either not responded
        # to or outright rejected reviewing this document in the past
        rejecting_reviewer_ids = review_req.doc.reviewrequest_set.filter(
            reviewassignment__state__slug__in=('rejected', 'no-response')
        ).values_list(
            'reviewassignment__reviewer__person_id', flat=True
        )

        # Query the Email objects for reviewers who haven't rejected or
        # not responded to this document in the past
        field.queryset = field.queryset.filter(
            role__name="reviewer",
            role__group=review_req.team
        ).exclude( person_id__in=rejecting_reviewer_ids )

        one_assignment = (review_req.reviewassignment_set
                          .exclude(state__slug__in=('rejected', 'no-response'))
                          .first())
        if one_assignment:
            field.initial = one_assignment.reviewer_id

        choices = self.recommended_assignment_order(field.queryset, review_req)
        if not field.required:
            choices = [("", field.empty_label)] + choices

        field.choices = choices
        
    def recommended_assignment_order(self, email_queryset, review_req):
        """
        Determine the recommended assignment order for a review request,
        choosing from the reviewers in email_queryset, which should be a queryset
        returning Email objects.
        """
        if review_req.team != self.team:
            raise ValueError('Reviewer queue policy was passed a review request belonging to a different team.')            
        resolver = AssignmentOrderResolver(
            email_queryset,
            review_req,
            self._filter_unavailable_reviewers(
                self.default_reviewer_rotation_list(include_unavailable=True),
                review_req,
            )
        )
        return [(r['email'].pk, r['label']) for r in resolver.determine_ranking()]
        
    def _filter_unavailable_reviewers(self, reviewers, review_req=None):
        """Remove any reviewers who are not available for the specified review request
        
        Reviewers who have an unavailability reason of 'unavailable' are always excluded from the
        output.
        
        If review_req is specified, 'canfinish' reviewers who have previously completed a review of
        the doc in the ReviewRequest will be treated as available.
        
        If no review_req is None, reviewers who are 'canfinish' for *any* review are included in the
        output. Only 'unavailable' reviewers are excluded. In this case, the caller must account for
        these 'canfinish' reviewers only being available for some reviews. 
        
        If multiple UnavailablePeriods apply, a 'canfinish' will take priority over an 'unavailable'.
        """
        unavailable_periods = current_unavailable_periods_for_reviewers(self.team)
        if len(unavailable_periods) == 0:
            return reviewers.copy()  # nothing to do

        available_reviewers = []
        if review_req:
            previous_reviewers = persons_with_previous_review(self.team,
                                                              review_req,
                                                              [r.pk for r in reviewers],
                                                              'completed')
        else:
            # treat all reviewers as previous_reviewers if no review_req
            previous_reviewers = [r.pk for r in reviewers]

        for reviewer in reviewers:
            current_periods = unavailable_periods.get(reviewer.pk)
            keep = (current_periods is None) or (
                'canfinish' in [p.availability for p in current_periods] and reviewer.pk in previous_reviewers
            )
            if keep:
                available_reviewers.append(reviewer)
        return available_reviewers

    def _clear_request_next_assignment(self, person):
        s = self._reviewer_settings_for(person)
        s.request_assignment_next = False
        s.save()

    def _add_skip(self, person):
        s = self._reviewer_settings_for(person)
        s.skip_next += 1
        s.save()

    def _reviewer_settings_for(self, person):
        return ReviewerSettings.objects.get_or_create(team=self.team, person=person)[0]

                
class AssignmentOrderResolver:
    """
    The AssignmentOrderResolver resolves the "recommended assignment order",
    for a set of possible reviewers (email_queryset), a review request, and a
    rotation list.
    """
    def __init__(self, email_queryset, review_req, rotation_list):
        self.review_req = review_req
        self.doc = review_req.doc
        self.team = review_req.team
        self.rotation_list = rotation_list

        self.possible_emails = list(email_queryset)
        self.possible_person_ids = [e.person_id for e in self.possible_emails]
        self._collect_context()

    def _collect_context(self):
        """Collect all relevant data about this team, document and review request."""

        self.doc_aliases = DocAlias.objects.filter(docs=self.doc).values_list("name", flat=True)

        # This data is collected as a dict, keys being person IDs, values being numbers/objects.
        self.rotation_index = {p.pk: i for i, p in enumerate(self.rotation_list)}
        self.reviewer_settings = self._reviewer_settings_for_person_ids(self.possible_person_ids)
        self.days_needed_for_reviewers = days_needed_to_fulfill_min_interval_for_reviewers(self.team)
        self.connections = self._connections_with_doc(self.doc, self.possible_person_ids)
        self.unavailable_periods = current_unavailable_periods_for_reviewers(self.team)
        self.assignment_data_for_reviewers = latest_review_assignments_for_reviewers(self.team)
        self.unavailable_periods = current_unavailable_periods_for_reviewers(self.team)

        # This data is collected as a set of person IDs.
        self.has_completed_review_previous = persons_with_previous_review(
            self.team, self.review_req, self.possible_person_ids, 'completed'
        )
        self.has_rejected_review_previous = persons_with_previous_review(
            self.team, self.review_req, self.possible_person_ids, 'rejected'
        )
        self.wish_to_review = set(ReviewWish.objects.filter(team=self.team, person__in=self.possible_person_ids,
                                                       doc=self.doc).values_list("person", flat=True))
        
    def determine_ranking(self):
        """
        Determine the ranking of reviewers.
        Returns a list of tuples, each tuple containing an Email pk and an explanation label.
        """
        ranking = [self._ranking_for_email(e) for e in self.possible_emails if e.person_id in self.rotation_index]
        ranking.sort(key=lambda r: r["scores"], reverse=True)
        return ranking

    def _ranking_for_email(self, email):
        """
        Determine the ranking for a specific Email.
        Returns a dict with an email object, the scores and an explanation label.
        The scores are a list of individual scores, i.e. they are prioritised, not
        cumulative; so when comparing scores, elements later in the scores list
        will only matter if all earlier scores in the list are equal.
        
        Only valid if email.person_id is in self.rotation_index.
        """
        log.assertion('email.person_id in self.rotation_index')

        settings = self.reviewer_settings.get(email.person_id)
        scores = []
        explanations = []

        def add_boolean_score(direction, expr, explanation=None):
            scores.append(direction if expr else -direction)
            if expr and explanation:
                explanations.append(explanation)

        periods = self.unavailable_periods.get(email.person_id, [])
        def format_period(p):
            if p.end_date:
                res = "unavailable until {}".format(p.end_date.isoformat())
            else:
                res = "unavailable indefinitely"
            return "{} ({})".format(res, p.get_availability_display())
        if periods:
            explanations.append(", ".join(format_period(p) for p in periods))
            
        add_boolean_score(-1, email.person_id in self.has_rejected_review_previous, "rejected review of document before")
        add_boolean_score(+1, settings.request_assignment_next, "requested to be selected next for assignment")
        add_boolean_score(+1, email.person_id in self.has_completed_review_previous, "reviewed document before")
        add_boolean_score(+1, email.person_id in self.wish_to_review, "wishes to review document")
        add_boolean_score(-1, email.person_id in self.connections,
                          self.connections.get(email.person_id))  # reviewer is somehow connected: bad
        add_boolean_score(-1, settings.filter_re and any(
            re.search(settings.filter_re, n) for n in self.doc_aliases), "filter regexp matches")
        
        # minimum interval between reviews
        days_needed = self.days_needed_for_reviewers.get(email.person_id, 0)
        scores.append(-days_needed)
        if days_needed > 0:
            explanations.append("max frequency exceeded, ready in {} {}".format(days_needed,
                                                                                "day" if days_needed == 1 else "days"))
        # skip next value
        scores.append(-settings.skip_next)
        if settings.skip_next > 0:
            explanations.append("skip next {}".format(settings.skip_next))
            
        # index in the default rotation order
        index = self.rotation_index.get(email.person_id, 0)
        scores.append(-index)
        explanations.append("#{}".format(index + 1))
        
        # stats (for information, do not affect score)
        stats = self._collect_reviewer_stats(email)
        if stats:
            explanations.append(", ".join(stats))

        label = str(email.person)
        if explanations:
            label = "{}: {}".format(label, "; ".join(explanations))
        return {
            "email": email,
            "scores": scores,
            "label": label,
        }

    def _collect_reviewer_stats(self, email):
        """Collect statistics on past reviews for a particular Email."""
        stats = []
        assignment_data = self.assignment_data_for_reviewers.get(email.person_id, [])
        currently_open = sum(1 for d in assignment_data if d.state in ["assigned", "accepted"])
        pages = sum(
            rd.doc_pages for rd in assignment_data if rd.state in ["assigned", "accepted"])
        if currently_open > 0:
            stats.append("currently {count} open, {pages} pages".format(count=currently_open,
                                                                        pages=pages))
        could_have_completed = [d for d in assignment_data if
                                d.state in ["part-completed", "completed", "no-response"]]
        if could_have_completed:
            no_response = len([d for d in assignment_data if d.state == 'no-response'])
            if no_response:
                stats.append("%s no response" % no_response)
            part_completed = len([d for d in assignment_data if d.state == 'part-completed'])
            if part_completed:
                stats.append("%s partially complete" % part_completed)
            completed = len([d for d in assignment_data if d.state == 'completed'])
            if completed:
                stats.append("%s fully completed" % completed)
        return stats
            
    def _connections_with_doc(self, doc, person_ids):
        """
        Collect any connections any Person in person_ids has with a document.
        Returns a dict containing Person IDs that have a connection as keys,
        values being an explanation string, 
        """
        connections = {}
        # examine the closest connections last to let them override the label
        connections[doc.ad_id] = "is associated Area Director"
        for r in Role.objects.filter(group=doc.group_id,
                                     person__in=person_ids).select_related("name"):
            connections[r.person_id] = "is group {}".format(r.name)
        if doc.shepherd:
            connections[doc.shepherd.person_id] = "is shepherd of document"
        for author in DocumentAuthor.objects.filter(document=doc,
                                                    person__in=person_ids).values_list(
            "person", flat=True):
            connections[author] = "is author of document"
        return connections

    def _reviewer_settings_for_person_ids(self, person_ids):
        reviewer_settings = {
            r.person_id: r
            for r in ReviewerSettings.objects.filter(team=self.team, person__in=person_ids)
        }
        for p in person_ids:
            if p not in reviewer_settings:
                reviewer_settings[p] = ReviewerSettings(team=self.team,
                                                        filter_re=get_default_filter_re(p))
        return reviewer_settings
    

class RotateAlphabeticallyReviewerQueuePolicy(AbstractReviewerQueuePolicy):
    """
    A policy in which the default rotation list is based on last name, alphabetically.
    NextReviewerInTeam is used to store a pointer to where the queue is currently
    positioned.
    """
    def default_reviewer_rotation_list(self, include_unavailable=False):
        reviewers = super(
            RotateAlphabeticallyReviewerQueuePolicy, self
        ).default_reviewer_rotation_list(include_unavailable)

        reviewers.sort(key=lambda p: p.last_name())
        next_reviewer_index = 0
    
        next_reviewer_in_team = NextReviewerInTeam.objects.filter(team=self.team).select_related("next_reviewer").first()
        if next_reviewer_in_team:
            next_reviewer = next_reviewer_in_team.next_reviewer
    
            if next_reviewer not in reviewers:
                # If the next reviewer is no longer on the team,
                # advance to the person that would be after them in
                # the rotation. (Python will deal with too large slice indexes
                # so no harm done by using the index on the original list
                # afterwards)
                reviewers_with_next = reviewers[:] + [next_reviewer]
                reviewers_with_next.sort(key=lambda p: p.last_name())
                next_reviewer_index = reviewers_with_next.index(next_reviewer)
            else:
                next_reviewer_index = reviewers.index(next_reviewer)
    
        return reviewers[next_reviewer_index:] + reviewers[:next_reviewer_index]

    def return_reviewer_to_rotation_top(self, reviewer_person):
        # As RotateAlphabetically does not keep a full rotation list,
        # returning someone to a particular order is complex.
        # Instead, the "assign me next" flag is set.
        settings = self._reviewer_settings_for(reviewer_person)
        settings.request_assignment_next = True
        settings.save()

    def _update_skip_next(self, rotation_pks, assignee_person):
        """Decrement skip_next for all users skipped

        In addition to the base class behavior, this looks ahead to the next reviewer in the
        team and updates NextReviewerInTeam appropriately. Accounts for skip counts along the
        way.   
        """

        super(RotateAlphabeticallyReviewerQueuePolicy, self)._update_skip_next(rotation_pks,
                                                                               assignee_person)
        # All reviewers in the list ahead of the assignee have already had their skip_next
        # values decremented. Now need to update NextReviewerInTeam.
        
        # Copy and unfold the rotation list, putting the assignee at the front
        unfolded_rotation_pks = rotation_pks.copy()
        assignee_index = unfolded_rotation_pks.index(assignee_person.pk)
        unfolded_rotation_pks = unfolded_rotation_pks[assignee_index:] + unfolded_rotation_pks[:assignee_index]
        # Then remove the assignee
        unfolded_rotation_pks.pop(0)

        # Nothing to do if the assignee is the only person in the list
        if len(unfolded_rotation_pks) == 0:
            return
        
        # Get a map from person PK to their settings, if any
        rotation_settings = {
            settings.person_id: settings
            for settings in self.team.reviewersettings_set.filter(person__in=unfolded_rotation_pks)
        }

        # Update any skip_counts we skip while finding the next reviewer. Handle the case where all skip_count > 0.
        if len(rotation_settings) < len(unfolded_rotation_pks):
            min_skip_next = 0  # one or more reviewers has no settings object, so they have skip_count=0   
        else:
            min_skip_next = min([rs.skip_next for rs in rotation_settings.values()])

        next_reviewer_index = None
        for index, pk in enumerate(unfolded_rotation_pks):
            rs = rotation_settings.get(pk)
            if (rs is None) or (rs.skip_next == min_skip_next):
                next_reviewer_index = index
                break
            else:
                rs.skip_next = max(0, rs.skip_next - 1)  # ensure never negative
                
        log.assertion('next_reviewer_index is not None')  # some entry in the list must have the minimum value

        bulk_update_with_history(rotation_settings.values(),
                                 ReviewerSettings,
                                 ['skip_next'],
                                 default_change_reason='skipped')

        next_reviewer_pk = unfolded_rotation_pks[next_reviewer_index]
        NextReviewerInTeam.objects.update_or_create(
            team=self.team,
            defaults=dict(next_reviewer_id=next_reviewer_pk)
        )


class LeastRecentlyUsedReviewerQueuePolicy(AbstractReviewerQueuePolicy):
    """
    A policy where the default rotation list is based on the most recent
    assigned, accepted or completed review assignment.
    """
    def default_reviewer_rotation_list(self, include_unavailable=False):
        reviewers = super(
            LeastRecentlyUsedReviewerQueuePolicy, self
        ).default_reviewer_rotation_list(include_unavailable)

        reviewers_dict = {p.pk: p for p in reviewers}
        assignments = ReviewAssignment.objects.filter(
            review_request__team=self.team,
            state__in=['accepted', 'assigned', 'completed'],
            reviewer__person__in=reviewers,
        ).values('reviewer__person').annotate(most_recent=Max('assigned_on')).order_by('most_recent')

        reviewers_with_assignment = [
            reviewers_dict[assignment['reviewer__person']]
            for assignment in assignments
        ] 
        reviewers_without_assignment = set(reviewers) - set(reviewers_with_assignment)
        
        rotation_list = sorted(list(reviewers_without_assignment), key=lambda r: r.pk)
        rotation_list += reviewers_with_assignment
        return rotation_list

    def return_reviewer_to_rotation_top(self, reviewer_person):
        # Reviewer rotation for this policy ignores rejected/withdrawn
        # reviews, so it automatically adjusts the position of someone
        # who rejected a review and no further action is needed.
        pass


QUEUE_POLICY_NAME_MAPPING = {
    'RotateAlphabetically': RotateAlphabeticallyReviewerQueuePolicy,
    'LeastRecentlyUsed': LeastRecentlyUsedReviewerQueuePolicy,
}
