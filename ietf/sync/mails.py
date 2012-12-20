from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

from ietf.utils.mail import send_mail

from ietf.sync.discrepancies import find_discrepancies

def email_discrepancies(receivers):
    sections = find_discrepancies()

    send_mail(None,
              receivers,
              None,
              "Datatracker Sync Discrepancies Report",
              "sync/discrepancies_report.txt",
              dict(sections=sections,
                   url=settings.IDTRACKER_BASE_URL + urlreverse("ietf.sync.views.discrepancies"),
                   base_url=settings.IDTRACKER_BASE_URL,
                   ))


