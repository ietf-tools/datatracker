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


def policy_for_team(team):
    return RotateWithSkipReviewerPolicy()


class AbstractReviewerPolicy:

    def _unavailable_reviewers(self, team, dont_skip):
        # prune reviewers not in the rotation (but not the assigned
        # reviewer who must have been available for assignment anyway)
        reviewers_to_skip = set()

        unavailable_periods = current_unavailable_periods_for_reviewers(team)
        for person_id, periods in unavailable_periods.items():
            if periods and person_id not in dont_skip:
                reviewers_to_skip.add(person_id)
                
        days_needed_for_reviewers = days_needed_to_fulfill_min_interval_for_reviewers(team)
        for person_id, days_needed in days_needed_for_reviewers.items():
            if person_id not in dont_skip:
                reviewers_to_skip.add(person_id)
        return reviewers_to_skip


class RotateWithSkipReviewerPolicy(AbstractReviewerPolicy):
    # TODO : Change this field to deal with multiple already assigned reviewers???
    def setup_reviewer_field(self, field, review_req):
        field.queryset = field.queryset.filter(role__name="reviewer", role__group=review_req.team)
        one_assignment = review_req.reviewassignment_set.first()
        if one_assignment:
            field.initial = one_assignment.reviewer_id

        choices = self._make_assignment_choices(field.queryset, review_req)
        if not field.required:
            choices = [("", field.empty_label)] + choices

        field.choices = choices

    def _make_assignment_choices(self, email_queryset, review_req):
        doc = review_req.doc
        team = review_req.team

        possible_emails = list(email_queryset)
        possible_person_ids = [e.person_id for e in possible_emails]

        aliases = DocAlias.objects.filter(docs=doc).values_list("name", flat=True)

        # settings
        reviewer_settings = {
            r.person_id: r
            for r in ReviewerSettings.objects.filter(team=team, person__in=possible_person_ids)
        }

        for p in possible_person_ids:
            if p not in reviewer_settings:
                reviewer_settings[p] = ReviewerSettings(team=team,
                                                        filter_re=get_default_filter_re(p))

        # frequency
        days_needed_for_reviewers = days_needed_to_fulfill_min_interval_for_reviewers(team)

        # rotation
        rotation_index = {p.pk: i for i, p in enumerate(self.reviewer_rotation_list(team))}

        # previous review of document
        has_reviewed_previous = ReviewRequest.objects.filter(
            doc=doc,
            reviewassignment__reviewer__person__in=possible_person_ids,
            reviewassignment__state="completed",
            team=team,
        ).distinct()

        if review_req.pk is not None:
            has_reviewed_previous = has_reviewed_previous.exclude(pk=review_req.pk)

        has_reviewed_previous = set(
            has_reviewed_previous.values_list("reviewassignment__reviewer__person", flat=True))

        # review wishes
        wish_to_review = set(ReviewWish.objects.filter(team=team, person__in=possible_person_ids,
                                                       doc=doc).values_list("person", flat=True))

        # connections
        connections = {}
        # examine the closest connections last to let them override
        connections[doc.ad_id] = "is associated Area Director"
        for r in Role.objects.filter(group=doc.group_id,
                                     person__in=possible_person_ids).select_related("name"):
            connections[r.person_id] = "is group {}".format(r.name)
        if doc.shepherd:
            connections[doc.shepherd.person_id] = "is shepherd of document"
        for author in DocumentAuthor.objects.filter(document=doc,
                                                    person__in=possible_person_ids).values_list(
            "person", flat=True):
            connections[author] = "is author of document"

        # unavailable periods
        unavailable_periods = current_unavailable_periods_for_reviewers(team)

        # reviewers statistics
        assignment_data_for_reviewers = latest_review_assignments_for_reviewers(team)

        ranking = []
        for e in possible_emails:
            settings = reviewer_settings.get(e.person_id)

            # we sort the reviewers by separate axes, listing the most
            # important things first
            scores = []
            explanations = []

            def add_boolean_score(direction, expr, explanation=None):
                scores.append(direction if expr else -direction)
                if expr and explanation:
                    explanations.append(explanation)

            # unavailable for review periods
            periods = unavailable_periods.get(e.person_id, [])
            unavailable_at_the_moment = periods and not (
                    e.person_id in has_reviewed_previous and all(
                    p.availability == "canfinish" for p in periods))
            add_boolean_score(-1, unavailable_at_the_moment)

            def format_period(p):
                if p.end_date:
                    res = "unavailable until {}".format(p.end_date.isoformat())
                else:
                    res = "unavailable indefinitely"
                return "{} ({})".format(res, p.get_availability_display())

            if periods:
                explanations.append(", ".join(format_period(p) for p in periods))

            # misc
            add_boolean_score(+1, e.person_id in has_reviewed_previous, "reviewed document before")
            add_boolean_score(+1, e.person_id in wish_to_review, "wishes to review document")
            add_boolean_score(-1, e.person_id in connections,
                              connections.get(e.person_id))  # reviewer is somehow connected: bad
            add_boolean_score(-1, settings.filter_re and any(
                re.search(settings.filter_re, n) for n in aliases), "filter regexp matches")

            # minimum interval between reviews
            days_needed = days_needed_for_reviewers.get(e.person_id, 0)
            scores.append(-days_needed)
            if days_needed > 0:
                explanations.append("max frequency exceeded, ready in {} {}".format(days_needed,
                                                                                    "day" if days_needed == 1 else "days"))

            # skip next
            scores.append(-settings.skip_next)
            if settings.skip_next > 0:
                explanations.append("skip next {}".format(settings.skip_next))

            # index
            index = rotation_index.get(e.person_id, 0)
            scores.append(-index)
            explanations.append("#{}".format(index + 1))

            # stats
            stats = []
            assignment_data = assignment_data_for_reviewers.get(e.person_id, [])

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

            if stats:
                explanations.append(", ".join(stats))

            label = six.text_type(e.person)
            if explanations:
                label = "{}: {}".format(label, "; ".join(explanations))

            ranking.append({
                "email": e,
                "scores": scores,
                "label": label,
            })

        ranking.sort(key=lambda r: r["scores"], reverse=True)

        return [(r["email"].pk, r["label"]) for r in ranking]

    def possibly_advance_next_reviewer_for_team(self, team, assigned_review_to_person_id, add_skip=False):
        assert assigned_review_to_person_id is not None

        rotation_list = self.reviewer_rotation_list(team, skip_unavailable=True,
                                                    dont_skip=[assigned_review_to_person_id])

        def reviewer_at_index(i):
            if not rotation_list:
                return None
            return rotation_list[i % len(rotation_list)]

        def reviewer_settings_for(person_id):
            return (ReviewerSettings.objects.filter(team=team, person=person_id).first()
                    or ReviewerSettings(team=team, person_id=person_id))

        current_i = 0

        if assigned_review_to_person_id == reviewer_at_index(current_i):
            # move 1 ahead
            current_i += 1

        if add_skip:
            settings = reviewer_settings_for(assigned_review_to_person_id)
            settings.skip_next += 1
            settings.save()

        if not rotation_list:
            return

        while True:
            # as a clean-up step go through any with a skip next > 0
            current_reviewer_person_id = reviewer_at_index(current_i)
            settings = reviewer_settings_for(current_reviewer_person_id)
            if settings.skip_next > 0:
                settings.skip_next -= 1
                settings.save()
                current_i += 1
            else:
                nr = NextReviewerInTeam.objects.filter(team=team).first() or NextReviewerInTeam(
                    team=team)
                nr.next_reviewer_id = current_reviewer_person_id
                nr.save()

                break

    def reviewer_rotation_list(self, team, skip_unavailable=False, dont_skip=[]):
        reviewers = list(Person.objects.filter(role__name="reviewer", role__group=team))
        reviewers.sort(key=lambda p: p.last_name())
        next_reviewer_index = 0
    
        # now to figure out where the rotation is currently at
        saved_reviewer = NextReviewerInTeam.objects.filter(team=team).select_related("next_reviewer").first()
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
    
        reviewers_to_skip = []            
        if skip_unavailable:
            reviewers_to_skip = self._unavailable_reviewers(team, dont_skip)
            rotation_list = [p.pk for p in rotation_list if p.pk not in reviewers_to_skip]
    
        return rotation_list

