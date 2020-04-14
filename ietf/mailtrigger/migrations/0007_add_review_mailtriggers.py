# Copyright The IETF Trust 2018-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import migrations

def forward(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger','MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    review_assignment_reviewer = Recipient.objects.create(
        slug="review_assignment_reviewer",
        desc="The reviewer assigned to a review assignment",
        template="{% if not skip_review_reviewer %}{{review_assignment.reviewer.email_address}}{% endif %}",
    )
    review_assignment_review_req_by = Recipient.objects.create(
        slug="review_assignment_review_req_by",
        desc="The requester of an assigned review",
        template="{% if not skip_review_requested_by %}{{review_assignment.review_request.requested_by.email_address}}{% endif %}",
    )
    review_req_requested_by = Recipient.objects.create(
        slug="review_req_requested_by",
        desc="The requester of a review",
        template="{% if not skip_review_requested_by %}{{review_req.requested_by.email_address}}{% endif %}",
    )
    review_req_reviewers = Recipient.objects.create(
        slug="review_req_reviewers",
        desc="All reviewers assigned to a review request",
        template=None,
    )
    review_secretaries = Recipient.objects.create(
        slug="review_secretaries",
        desc="The secretaries of the review team of a review request or assignment",
        template=None,
    )
    Recipient.objects.create(
        slug="review_reviewer",
        desc="A single reviewer",
        template="{{reviewer.email_address}}",
    )

    review_assignment_changed = MailTrigger.objects.create(
        slug="review_assignment_changed",
        desc="Recipients for a change to a review assignment",
    )
    review_assignment_changed.to.set([review_assignment_review_req_by, review_assignment_reviewer,
                                      review_secretaries])

    review_req_changed = MailTrigger.objects.create(
        slug="review_req_changed",
        desc="Recipients for a change to a review request",
    )
    review_req_changed.to.set([review_req_requested_by, review_req_reviewers, review_secretaries])
    
    review_availability_changed = MailTrigger.objects.create(
        slug="review_availability_changed",
        desc="Recipients for a change to a reviewer's availability",
    )
    review_availability_changed.to.set(
        Recipient.objects.filter(slug__in=['review_reviewer', 'group_secretaries'])
    )


def reverse(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger','MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    MailTrigger.objects.filter(slug__in=[
        'review_assignment_changed', 'review_req_changed', 'review_availability_changed', 
    ]).delete()
    Recipient.objects.filter(slug__in=[
        'review_assignment_reviewer', 'review_assignment_review_req_by', 'review_req_requested_by',
        'review_req_reviewers', 'review_secretaries', 'review_reviewer',
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0006_sub_new_wg_00'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
