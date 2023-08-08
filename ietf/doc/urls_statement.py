# Copyright The IETF Trust 2023, All Rights Reserved

from django.conf import settings
from ietf.doc import views_statement
from ietf.utils.urls import url

urlpatterns = [
    url(r"^(?:%(rev)s/)?pdf/$" % settings.URL_REGEXPS, views_statement.serve_pdf),
    url(r"^submit/$", views_statement.submit),
]
