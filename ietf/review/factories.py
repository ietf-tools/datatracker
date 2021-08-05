# Copyright The IETF Trust 2016-2019, All Rights Reserved
import factory
import datetime

from ietf.review.models import ReviewTeamSettings, ReviewRequest, ReviewAssignment, ReviewerSettings
from ietf.name.models import ReviewTypeName, ReviewResultName


class ReviewTeamSettingsFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReviewTeamSettings

    group = factory.SubFactory('ietf.group.factories.GroupFactory',type_id='review')
    reviewer_queue_policy_id = 'RotateAlphabetically'

    @factory.post_generation
    def review_types(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            obj.review_types.set(ReviewTypeName.objects.filter(slug__in=extracted))
        else:
            obj.review_types.set(ReviewTypeName.objects.filter(slug__in=('early','lc','telechat')))

    @factory.post_generation
    def review_results(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            obj.review_results.set(ReviewResultName.objects.filter(slug__in=extracted))
        else:
            obj.review_results.set(ReviewResultName.objects.filter(slug__in=('not-ready','right-track','almost-ready','ready-issues','ready-nits','ready')))

class ReviewRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReviewRequest

    state_id = 'requested'
    type_id = 'lc'
    doc = factory.SubFactory('ietf.doc.factories.DocumentFactory',type_id='draft')
    team = factory.SubFactory('ietf.group.factories.ReviewTeamFactory',type_id='review')
    deadline = datetime.datetime.today()+datetime.timedelta(days=14)
    requested_by = factory.SubFactory('ietf.person.factories.PersonFactory')

class ReviewAssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReviewAssignment

    review_request = factory.SubFactory('ietf.review.factories.ReviewRequestFactory')
    state_id = 'assigned'
    reviewer = factory.SubFactory('ietf.person.factories.EmailFactory')
    assigned_on = datetime.datetime.now()

class ReviewerSettingsFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReviewerSettings

    team = factory.SubFactory('ietf.group.factories.ReviewTeamFactory')
    person = factory.SubFactory('ietf.person.factories.PersonFactory')
