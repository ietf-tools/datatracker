# Copyright The IETF Trust 2026, All Rights Reserved
"""Tests of forms in the Doc application"""

from django.core.exceptions import ValidationError

from ietf.doc.forms import ExtResourceForm, SingleExtResourceForm
from ietf.doc.models import DocExtResource
from ietf.name.models import ExtResourceName, ExtResourceTypeName
from ietf.submit.models import SubmissionExtResource
from ietf.utils.test_utils import TestCase
from ietf.utils.validators import validate_external_resource_value


class SingleExtResourceFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ExtResourceName.objects.create(
            slug="keymaster", name="Keymaster", type_id="email"
        )

    def test_valid_by_type(self):
        for name, value in (
            ("webpage", "https://example.com/a/page"),
            ("github_username", "githubuser"),
            ("keymaster", "keymaster@example.org"),
            ("github_org", "https://github.com/some_org"),
            ("github_repo", "https://github.com/some/repo"),
            ("jabber_room", "xmpp:mars@jabber.example.com"),
        ):
            form = SingleExtResourceForm(
                data=dict(name=name, value=value, display_name="")
            )
            self.assertTrue(
                form.is_valid(), f"{name} {value} should be valid: {form.errors}"
            )
            self.assertEqual(form.instance.name_id, name)
            self.assertEqual(form.instance.value, value)

    def test_invalid_by_type(self):
        for name, value in (
            ("webpage", "/not/a/good/url"),
            ("github_repo", "https://github3.com/some/repo"),
            ("github_org", "https://github.com/not/an_org"),
            ("jabber_room", "https://jabber.example.com/mars"),
            ("keymaster", "not-an-email"),
        ):
            form = SingleExtResourceForm(
                data=dict(name=name, value=value, display_name="")
            )
            self.assertFalse(form.is_valid(), f"{name} {value} should not be valid")

    def test_unknown_tag(self):
        form = SingleExtResourceForm(
            data=dict(name="notavalidtag", value="blahblahblah")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("webpage", str(form.errors["name"]))

    def test_value_length_limit(self):
        """Model field limits are enforced as form errors, not database errors"""
        too_long = "https://example.com/" + "x" * 2083
        form = SingleExtResourceForm(data=dict(name="webpage", value=too_long))
        self.assertFalse(form.is_valid())
        self.assertIn("value", form.errors)

    def test_display_name_length_limit(self):
        form = SingleExtResourceForm(
            data=dict(
                name="webpage", value="https://example.com/", display_name="x" * 256
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("display_name", form.errors)

    def test_value_required(self):
        form = SingleExtResourceForm(data=dict(name="webpage", value=""))
        self.assertFalse(form.is_valid())
        self.assertIn("value", form.errors)

    def test_display_name_optional(self):
        form = SingleExtResourceForm(
            data=dict(name="webpage", value="https://example.com/")
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.instance.display_name, "")

    def test_instance_determines_model(self):
        """The instance passed in, not Meta.model, decides what is built"""
        data = dict(name="webpage", value="https://example.com/")

        form = SingleExtResourceForm(data=data)
        self.assertTrue(form.is_valid())
        self.assertIsInstance(form.instance, DocExtResource)
        self.assertIsNone(form.instance.pk)

        form = SingleExtResourceForm(data=data, instance=SubmissionExtResource())
        self.assertTrue(form.is_valid())
        self.assertIsInstance(form.instance, SubmissionExtResource)
        self.assertIsNone(form.instance.pk)


class ExtResourceFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ExtResourceName.objects.create(
            slug="keymaster", name="Keymaster", type_id="email"
        )

    def test_empty(self):
        form = ExtResourceForm(data=dict(resources=""))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["resources"], [])

    def test_multiple_lines(self):
        form = ExtResourceForm(
            data=dict(
                resources="""
            github_repo https://github.com/some/repo Some display text
            github_org https://github.com/totally_some_org
            github_username githubuser
            webpage http://example.com/http/is/fine
            keymaster keymaster@example.org (Group Rooter)
        """
            )
        )
        self.assertTrue(form.is_valid(), form.errors)
        resources = form.cleaned_data["resources"]
        self.assertEqual(len(resources), 5)
        self.assertTrue(all(isinstance(r, DocExtResource) for r in resources))
        self.assertTrue(all(r.pk is None for r in resources))
        self.assertEqual(
            [r.name_id for r in resources],
            ["github_repo", "github_org", "github_username", "webpage", "keymaster"],
        )
        self.assertEqual(resources[0].display_name, "Some display text")
        self.assertEqual(resources[1].display_name, "")
        self.assertEqual(resources[4].display_name, "Group Rooter")

    def test_too_few_fields(self):
        form = ExtResourceForm(data=dict(resources="webpage"))
        self.assertFalse(form.is_valid())
        self.assertIn("Too few fields", str(form.errors["resources"]))

    def test_errors_are_rolled_up_per_line(self):
        form = ExtResourceForm(
            data=dict(
                resources="\n".join(
                    [
                        "webpage /not/a/good/url",
                        "notavalidtag blahblahblah",
                    ]
                )
            )
        )
        self.assertFalse(form.is_valid())
        errors = form.errors["resources"]
        self.assertEqual(len(errors), 2)
        self.assertIn("webpage /not/a/good/url", errors[0])
        self.assertIn("notavalidtag blahblahblah", errors[1])

    def test_one_bad_line_invalidates_the_form(self):
        form = ExtResourceForm(
            data=dict(
                resources="\n".join(
                    [
                        "webpage https://example.com/a/page",
                        "webpage /not/a/good/url",
                    ]
                )
            )
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors["resources"]), 1)

    def test_extresource_model(self):
        form = ExtResourceForm(
            data=dict(resources="webpage https://example.com/a/page"),
            extresource_model=SubmissionExtResource,
        )
        self.assertTrue(form.is_valid(), form.errors)
        resource = form.cleaned_data["resources"][0]
        self.assertIsInstance(resource, SubmissionExtResource)
        self.assertIsNone(resource.pk)

    def test_initial_round_trip(self):
        resources = [
            DocExtResource(name_id="webpage", value="https://example.com/a/page"),
            DocExtResource(
                name_id="github_repo",
                value="https://github.com/some/repo",
                display_name="Some display text",
            ),
        ]
        initial = ExtResourceForm(initial=dict(resources=resources)).initial[
            "resources"
        ]
        form = ExtResourceForm(data=dict(resources=initial))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            [
                (r.name_id, r.value, r.display_name)
                for r in form.cleaned_data["resources"]
            ],
            [(r.name_id, r.value, r.display_name) for r in resources],
        )


class ExtResourceModelTests(TestCase):
    def test_clean_validates_value(self):
        resource = DocExtResource(name_id="webpage", value="/not/a/good/url")
        with self.assertRaises(ValidationError):
            resource.full_clean(exclude=["doc"])

    def test_clean_without_name(self):
        """clean() runs even when clean_fields() has already rejected the name"""
        for resource in (
            DocExtResource(value="https://example.com/"),
            DocExtResource(name_id="notavalidtag", value="https://example.com/"),
        ):
            with self.assertRaises(ValidationError):
                resource.full_clean(exclude=["doc"])


class ValidateExternalResourceValueTests(TestCase):
    def test_url(self):
        validate_external_resource_value(
            ExtResourceName.objects.get(slug="webpage"), "https://example.com/"
        )
        with self.assertRaises(ValidationError):
            validate_external_resource_value(
                ExtResourceName.objects.get(slug="webpage"), "not a url"
            )

    def test_github(self):
        github_org = ExtResourceName.objects.get(slug="github_org")
        validate_external_resource_value(github_org, "https://github.com/some_org")
        for bad in (
            "https://github3.com/some_org",
            "https://github.com/some/org",
            "ftp://github.com/some_org",
        ):
            with self.assertRaises(ValidationError):
                validate_external_resource_value(github_org, bad)

    def test_xmpp(self):
        jabber_room = ExtResourceName.objects.get(slug="jabber_room")
        validate_external_resource_value(jabber_room, "xmpp:mars@jabber.example.com")
        with self.assertRaises(ValidationError):
            validate_external_resource_value(
                jabber_room, "https://jabber.example.com/mars"
            )

    def test_email(self):
        name = ExtResourceName.objects.create(
            slug="keymaster", name="Keymaster", type_id="email"
        )
        validate_external_resource_value(name, "keymaster@example.org")
        with self.assertRaises(ValidationError):
            validate_external_resource_value(name, "not-an-email")

    def test_string(self):
        validate_external_resource_value(
            ExtResourceName.objects.get(slug="github_username"), "anything at all"
        )

    def test_unknown_type(self):
        ExtResourceTypeName.objects.create(slug="mystery", name="Mystery")
        name = ExtResourceName.objects.create(
            slug="mystery", name="Mystery", type_id="mystery"
        )
        with self.assertRaises(ValidationError):
            validate_external_resource_value(name, "whatever")
