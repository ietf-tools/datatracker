# Copyright The IETF Trust 2016-2019, All Rights Reserved

from __future__ import absolute_import, print_function, unicode_literals

import re

import six

from ietf.doc.models import DocumentAuthor, DocAlias
from ietf.group.models import Role
from ietf.person.models import Person
import debug                            # pyflakes:ignore
from ietf.review.models import NextReviewerInTeam, ReviewerSettings, ReviewWish, ReviewRequest
from ietf.review.utils import (current_unavailable_periods_for_reviewers,
                               days_needed_to_fulfill_min_interval_for_reviewers, 
                               get_default_filter_re,
                               latest_review_assignments_for_reviewers)

"""
This file contains policies regarding reviewer queues.
The policies are documented in more detail on:
https://trac.tools.ietf.org/tools/ietfdb/wiki/ReviewerQueuePolicy
Terminology used here should match terminology used in that document.
"""


def get_reviewer_queue_policy(team):
    return RotateWithSkipReviewerQueuePolicy(team)


class AbstractReviewerQueuePolicy:
    def __init__(self, team):
        self.team = team
        
    def default_reviewer_rotation_list(self, dont_skip_person_ids=None):
        """
        Return a list of reviewers (Person objects) in the default reviewer rotation for a policy.
        """
        raise NotImplementedError  # pragma: no cover
    
    def update_policy_state_for_assignment(self, assignee_person_id, add_skip=False):
        """
        Update the internal state of a policy to reflect an assignment. 
        """
        raise NotImplementedError  # pragma: no cover

    # TODO : Change this field to deal with multiple already assigned reviewers???
    def setup_reviewer_field(self, field, review_req):
        """
        Fill a choice field with the recommended assignment order of reviewers for a review request.
        The field should be an instance similar to
            PersonEmailChoiceField(label="Assign Reviewer", empty_label="(None)")
        """
        field.queryset = field.queryset.filter(role__name="reviewer", role__group=review_req.team)
        one_assignment = review_req.reviewassignment_set.first()
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
            raise ValueError('Reviewer queue policy was passed review request belonging to different team.')            
        resolver = AssignmentOrderResolver(email_queryset, review_req, self.default_reviewer_rotation_list())
        return [(r['email'].pk, r['label']) for r in resolver.determine_ranking()]
        
    def _entirely_unavailable_reviewers(self, dont_skip_person_ids=None):
        """
        Return a set of PKs of Persons that should not be considered
        to be in the rotation list at all. 
        """
        reviewers_to_skip = set()
        if not dont_skip_person_ids:
            dont_skip_person_ids = []

        unavailable_periods = current_unavailable_periods_for_reviewers(self.team)
        for person_id, periods in unavailable_periods.items():
            if periods and person_id not in dont_skip_person_ids and not any(p.availability == "canfinish" for p in periods):
                reviewers_to_skip.add(person_id)
                
        return reviewers_to_skip
                

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
        self.reviewer_settings = self._reviewer_settings_for_person_ids(self.possible_person_ids)
        self.days_needed_for_reviewers = days_needed_to_fulfill_min_interval_for_reviewers(self.team)
        self.rotation_index = {p.pk: i for i, p in enumerate(self.rotation_list)}

        # This data is collected as a set of person IDs.
        self.has_reviewed_previous = self._persons_with_previous_review(self.review_req, self.possible_person_ids)
        self.wish_to_review = set(ReviewWish.objects.filter(team=self.team, person__in=self.possible_person_ids,
                                                       doc=self.doc).values_list("person", flat=True))

        self.connections = self._connections_with_doc(self.doc, self.possible_person_ids)
        self.unavailable_periods = current_unavailable_periods_for_reviewers(self.team)
        self.assignment_data_for_reviewers = latest_review_assignments_for_reviewers(self.team)
        self.unavailable_periods = current_unavailable_periods_for_reviewers(self.team)
        
    def determine_ranking(self):
        """
        Determine the ranking of reviewers.
        Returns a list of tuples, each tuple containing an Email pk and an explanation label.
        """
        ranking = []
        for e in self.possible_emails:
            ranking_for_email = self._ranking_for_email(e)
            if ranking_for_email:
                ranking.append(ranking_for_email)

        ranking.sort(key=lambda r: r["scores"], reverse=True)
        return ranking

    def _ranking_for_email(self, email):
        """
        Determine the ranking for a specific Email.
        Returns a dict with an email object, the scores and an explanation label.
        The scores are a list of individual scores, i.e. they are prioritised, not
        cumulative.
        """
        settings = self.reviewer_settings.get(email.person_id)
        scores = []
        explanations = []

        def add_boolean_score(direction, expr, explanation=None):
            scores.append(direction if expr else -direction)
            if expr and explanation:
                explanations.append(explanation)

        if email.person_id not in self.rotation_index:
            return

        # If a reviewer is unavailable, they are ignored.
        periods = self.unavailable_periods.get(email.person_id, [])
        unavailable_at_the_moment = periods and not (
            email.person_id in self.has_reviewed_previous and
            all(p.availability == "canfinish" for p in periods)
        )
        if unavailable_at_the_moment:
            return
        
        def format_period(p):
            if p.end_date:
                res = "unavailable until {}".format(p.end_date.isoformat())
            else:
                res = "unavailable indefinitely"
            return "{} ({})".format(res, p.get_availability_display())
        if periods:
            explanations.append(", ".join(format_period(p) for p in periods))
            
        # misc
        add_boolean_score(+1, email.person_id in self.has_reviewed_previous, "reviewed document before")
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
        # skip next
        scores.append(-settings.skip_next)
        if settings.skip_next > 0:
            explanations.append("skip next {}".format(settings.skip_next))
            
        # index
        index = self.rotation_index.get(email.person_id, 0)
        scores.append(-index)
        explanations.append("#{}".format(index + 1))
        
        # stats (for information, do not affect score)
        stats = self._collect_reviewer_stats(email)
        if stats:
            explanations.append(", ".join(stats))

        label = six.text_type(email.person)
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

    def _persons_with_previous_review(self, review_req, possible_person_ids):
        """
        Collect anyone in possible_person_ids that have reviewed the request before.
        Returns a set with Person IDs of anyone who has.
        """
        has_reviewed_previous = ReviewRequest.objects.filter(
            doc=review_req.doc,
            reviewassignment__reviewer__person__in=possible_person_ids,
            reviewassignment__state="completed",
            team=self.team,
        ).distinct()
        if review_req.pk is not None:
            has_reviewed_previous = has_reviewed_previous.exclude(pk=review_req.pk)
        has_reviewed_previous = set(
            has_reviewed_previous.values_list("reviewassignment__reviewer__person", flat=True))
        return has_reviewed_previous
    
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
    

class RotateWithSkipReviewerQueuePolicy(AbstractReviewerQueuePolicy):

    def update_policy_state_for_assignment(self, assignee_person, add_skip=False):
        print('====================')
        assert assignee_person is not None

        rotation_list = self.default_reviewer_rotation_list(dont_skip_person_ids=[assignee_person.pk])

        def reviewer_at_index(i):
            if not rotation_list:
                return None
            return rotation_list[i % len(rotation_list)]

        def reviewer_settings_for(person):
            return (ReviewerSettings.objects.filter(team=self.team, person=person).first()
                    or ReviewerSettings(team=self.team, person=person))

        if not rotation_list:
            return
        
        rotation_list_without_skip = [r for r in rotation_list if not reviewer_settings_for(r).skip_next]
        print('input: {} assigned'.format(assignee_person))
        print('with skipped {}'.format([r for r in rotation_list]))
        print('without skip {}'.format([r for r in rotation_list_without_skip]))
        print('skip counts {}'.format([(r, reviewer_settings_for(r).skip_next) for r in rotation_list]))
        in_order_assignment = rotation_list_without_skip[0] == assignee_person
        print('in order: {}'.format(in_order_assignment))
        
        # Loop through the list until finding the first person with skip_next=0,
        # who is not the current assignee. Anyone with skip_next>0 encountered before
        # has their skip_next decreased.
        current_idx = 0
        while in_order_assignment:
            current_idx_person = reviewer_at_index(current_idx)
            settings = reviewer_settings_for(current_idx_person)
            print('evaluating {} with skip_next {}, assignee {}'.format(current_idx_person, settings.skip_next, assignee_person))
            if settings.skip_next > 0:
                print('dropping skip_next')
                settings.skip_next -= 1
                settings.save()
            elif current_idx_person != assignee_person:
                print('nr appointed')
                nr = NextReviewerInTeam.objects.filter(team=self.team).first() or NextReviewerInTeam(
                    team=self.team)
                nr.next_reviewer = current_idx_person
                nr.save()

                break
            current_idx += 1
            
        if add_skip:
            print('raising skip count for assignee')
            settings = reviewer_settings_for(assignee_person)
            settings.skip_next += 1
            settings.save()

    def default_reviewer_rotation_list(self, include_unavailable=False, dont_skip_person_ids=None):
        reviewers = list(Person.objects.filter(role__name="reviewer", role__group=self.team))
        reviewers.sort(key=lambda p: p.last_name())
        next_reviewer_index = 0
    
        # now to figure out where the rotation is currently at
        saved_reviewer = NextReviewerInTeam.objects.filter(team=self.team).select_related("next_reviewer").first()
        if saved_reviewer:
            n = saved_reviewer.next_reviewer
    
            if n not in reviewers:
                # saved reviewer might not still be here, if not just
                # insert and use that position (Python will wrap around,
                # so no harm done by using the index on the original list
                # afterwards)
                reviewers_with_next = reviewers[:] + [n]
                reviewers_with_next.sort(key=lambda p: p.last_name())
                next_reviewer_index = reviewers_with_next.index(n)
            else:
                next_reviewer_index = reviewers.index(n)
    
        rotation_list = reviewers[next_reviewer_index:] + reviewers[:next_reviewer_index]
    
        if not include_unavailable:
            reviewers_to_skip = self._entirely_unavailable_reviewers(dont_skip_person_ids)
            rotation_list = [p for p in rotation_list if p.pk not in reviewers_to_skip]
        
        return rotation_list

