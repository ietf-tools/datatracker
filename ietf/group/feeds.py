# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
from django import forms
from django.contrib.syndication.views import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed
from django.urls import reverse as urlreverse
from django.utils.html import strip_tags
from django.template.defaultfilters import truncatewords

from ietf.review.models import ReviewAssignment
from ietf.group.models import Group, GroupEvent
from ietf.doc.models import DocEvent
from ietf.utils.timezone import datetime_today, DEADLINE_TZINFO

class GroupChangesFeed(Feed):
    feed_type = Atom1Feed
    description_template = "group/feed_item_description.html"

    def get_object(self, request, acronym):
        return Group.objects.get(acronym=acronym)

    def title(self, obj):
        return "Changes for %s %s" % (obj.acronym, obj.type)

    def link(self, obj):
        if not obj:
            raise FeedDoesNotExist
        return obj.about_url()

    def description(self, obj):
        return self.title(obj)

    def items(self, obj):
        events = list(obj.groupevent_set.all().select_related("group"))
        if obj.charter:
            events += list(obj.charter.docevent_set.all())

        events.sort(key=lambda e: (e.time, e.id), reverse=True)

        return events

    def item_link(self, obj):
        if isinstance(obj, DocEvent):
            return urlreverse("ietf.doc.views_doc.document_main", kwargs={'name': obj.doc.name })
        elif isinstance(obj, GroupEvent):
            return obj.group.about_url()

    def item_pubdate(self, obj):
        return obj.time

    def item_title(self, obj):
        title = "%s - %s" % (truncatewords(strip_tags(obj.desc), 10), obj.by)
        if isinstance(obj, DocEvent):
            title = "Chartering: %s" % title

        return title

class ReviewRequestFeedForm(forms.Form):
    since = forms.IntegerField(min_value=1, max_value = 9999, required=False)
    reviewer_email = forms.EmailField(required=False)

class ReviewRequestFeed(Feed):
    feed_type = Atom1Feed
    description_template = "group/feed_request_description.html"
    reviewer_email = None
    date_limit = None
    acronym = None

    def get_object(self, request, acronym):
        self.acronym = acronym
        group = Group.objects.get(acronym=acronym)
        if not group:
            raise FeedDoesNotExist
        if not group.features.has_reviews:
            raise FeedDoesNotExist

        params = ReviewRequestFeedForm(request.GET)
        if not params.is_valid():
            raise FeedDoesNotExist
        self.reviewer_email = params.cleaned_data["reviewer_email"] or None
        since = params.cleaned_data["since"] or None
        if since:
            self.date_limit = datetime.timedelta(days = since)

        return group

    def title(self, obj):
        return "Changes for %s %s" % (obj.acronym, obj.type)

    def link(self, obj):
        return obj.about_url()

    def description(self, obj):
        return self.title(obj)

    def items(self, obj):
        if self.reviewer_email:
            history = ReviewAssignment.history.model.objects.filter(
                review_request__team__acronym=self.acronym,
                reviewer=self.reviewer_email)
        else:
            history = ReviewAssignment.history.model.objects.filter(
                review_request__team__acronym=obj.acronym)
        if self.date_limit:
            history = history.filter(
                review_request__time__gte=datetime_today(DEADLINE_TZINFO) -
                self.date_limit)
        return history

    def item_link(self, item):
        return urlreverse('ietf.doc.views_review.review_request',
                          kwargs=dict(name=item.review_request.doc.name,
                                      request_id=item.review_request.pk))

    def item_pubdate(self, item):
        return item.history_date

    def item_title(self, item):
        title = "{} {} review for {} by {} state {}".format(item.review_request.type.name, item.review_request.team.acronym.upper(), item.review_request.doc, item.reviewer.person, item.state)
        return title

    def item_author_name(self, item):
        return item.reviewer.person

    def item_author_email(self, item):
        return item.reviewer.email_address()
