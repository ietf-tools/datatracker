# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
from celery import shared_task

from .views import generate_agenda_data


@shared_task
def agenda_data_refresh():
    generate_agenda_data(force_refresh=True)
