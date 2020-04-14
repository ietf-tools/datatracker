# Copyright The IETF Trust 2007, All Rights Reserved

# Portion Copyright (C) 2008-2009 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions 
# are met:
# 
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
# 
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from django.views.generic import RedirectView
from django.conf import settings

from ietf.iesg import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^telechat/.*$', RedirectView.as_view(url='https://www.ietf.org/iesg/minutes.html', permanent=True)),
    url(r'^ann/(?:ind|new|prev)/$', RedirectView.as_view(url="/iesg/decisions/", permanent=True)),
    url(r'^telechatdates/$', RedirectView.as_view(url='/admin/iesg/telechatdate/', permanent=True)),

    url(r'^decisions/(?:(?P<year>[0-9]{4})/)?$', views.review_decisions),
    url(r'^agenda/(?:%(date)s/)?$' % settings.URL_REGEXPS, views.agenda),
    url(r'^agenda/(?:%(date)s/)?agenda.txt$' % settings.URL_REGEXPS, views.agenda_txt),
    url(r'^agenda/(?:%(date)s/)?agenda.json$' % settings.URL_REGEXPS, views.agenda_json),
    url(r'^agenda/(?:%(date)s/)?scribe_template.html$' % settings.URL_REGEXPS, views.agenda_scribe_template),
    url(r'^agenda/(?:%(date)s/)?moderator_package.html$' % settings.URL_REGEXPS, views.agenda_moderator_package),
    url(r'^agenda/(?:%(date)s/)?agenda_package.txt$' % settings.URL_REGEXPS, views.agenda_package),

    url(r'^agenda/documents.txt$', views.agenda_documents_txt),
    url(r'^agenda/documents/$', views.agenda_documents),
    url(r'^past/documents/$', views.past_documents),
    url(r'^agenda/telechat-(?:%(date)s-)?docs.tgz' % settings.URL_REGEXPS, views.telechat_docs_tarfile),
    url(r'^discusses/$', views.discusses),
    url(r'^milestones/$', views.milestones_needing_review),
    url(r'^photos/$', views.photos),
]
