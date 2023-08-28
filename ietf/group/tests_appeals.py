# Copyright The IETF Trust 2023, All Rights Reserved

import debug    # pyflakes: ignore
import datetime

from pyquery import PyQuery

from django.urls import reverse as urlreverse

from ietf.utils.test_utils import login_testing_unauthorized, TestCase
from ietf.group.factories import (
    AppealFactory,
    AppealArtifactFactory,
)
class AppealTests(TestCase):

    def test_download_name(self):
        artifact = AppealArtifactFactory()
        self.assertEqual(artifact.download_name(),f"{artifact.date}-appeal.md")
        artifact = AppealArtifactFactory(content_type="application/pdf",artifact_type__slug="response")
        self.assertEqual(artifact.download_name(),f"{artifact.date}-response.pdf")


    def test_appeal_list_view(self):
        appeal_date = datetime.date.today()-datetime.timedelta(days=14)
        response_date = appeal_date+datetime.timedelta(days=8)
        appeal = AppealFactory(name="A name to look for", date=appeal_date)
        appeal_artifact = AppealArtifactFactory(appeal=appeal, artifact_type__slug="appeal", date=appeal_date)
        response_artifact = AppealArtifactFactory(appeal=appeal, artifact_type__slug="response", content_type="application/pdf", date=response_date)

        url = urlreverse("ietf.group.views.appeals", kwargs=dict(acronym="iab"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("#appeals > tbody > tr")), 1)
        self.assertEqual(q("#appeal-1-date").text(), f"{appeal_date}")
        self.assertEqual(f"{appeal_artifact.display_title()} - {appeal_date}", q("#artifact-1-1").text())
        self.assertEqual(f"{response_artifact.display_title()} - {response_date}", q("#artifact-1-2").text())
        self.assertIsNone(q("#artifact-1-1").attr("download"))
        self.assertEqual(q("#artifact-1-2").attr("download"), response_artifact.download_name())

    def test_markdown_view(self):
        artifact = AppealArtifactFactory()
        url = urlreverse("ietf.group.views.appeal_artifact", kwargs=dict(acronym="iab", artifact_id=artifact.pk))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(q("#content>p>strong").text(),"Markdown")
        self.assertIsNone(q("#content a").attr("download"))
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(q("#content a").attr("download"), artifact.download_name())

    def test_markdown_download(self):
        artifact = AppealArtifactFactory()
        url = urlreverse("ietf.group.views.appeal_artifact_markdown", kwargs=dict(acronym="iab", artifact_id=artifact.pk))
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertContains(r, "**Markdown**", status_code=200)

    def test_pdf_download(self):
        artifact = AppealArtifactFactory(content_type="application/pdf") # The bits won't _really_ be pdf
        url = urlreverse("ietf.group.views.appeal_artifact", kwargs=dict(acronym="iab", artifact_id=artifact.pk))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get("Content-Disposition"), f'attachment; filename="{artifact.download_name()}"')
        self.assertEqual(r.get("Content-Type"), artifact.content_type)
        self.assertEqual(r.content, artifact.bits.tobytes())

