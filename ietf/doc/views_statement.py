# Copyright The IETF Trust 2023-2025, All Rights Reserved
from django.contrib import messages

import debug  # pyflakes: ignore

from pathlib import Path

from django import forms
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.views.decorators.cache import cache_control
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string

from ietf.doc.forms import ChangeStatementStateForm
from ietf.doc.utils import add_state_change_event
from ietf.utils import markdown
from django.utils.html import escape

from ietf.doc.models import Document, DocEvent, NewRevisionDocEvent, State
from ietf.group.models import Group
from ietf.ietfauth.utils import role_required
from ietf.utils.text import xslugify
from ietf.utils.textupload import get_cleaned_text_file_content

CONST_PDF_REV_NOTICE = "The current revision of this statement is in pdf format"


@cache_control(max_age=3600)
def serve_pdf(self, name, rev=None):
    doc = get_object_or_404(Document, name=name)
    if rev is None:
        rev = doc.rev
    p = Path(doc.get_file_path()).joinpath(f"{doc.name}-{rev}.pdf")
    if not p.exists():
        raise Http404
    else:
        return FileResponse(p.open(mode="rb"), content_type="application/pdf")


class StatementUploadForm(forms.Form):
    ACTIONS = [
        ("enter", "Enter content directly"),
        ("upload", "Upload content from file"),
    ]
    statement_submission = forms.ChoiceField(choices=ACTIONS, widget=forms.RadioSelect)
    statement_file = forms.FileField(
        label="Markdown or PDF source file to upload", required=False
    )
    statement_content = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 30}), required=False, strip=False
    )

    def clean(self):
        def require_field(f):
            if not self.cleaned_data.get(f):
                self.add_error(f, forms.ValidationError("You must fill in this field."))
                return False
            else:
                return True

        submission_method = self.cleaned_data.get("statement_submission")
        markdown_content = ""
        if submission_method == "enter":
            if require_field("statement_content"):
                markdown_content = self.cleaned_data["statement_content"].replace(
                    "\r", ""
                )
                default_content = render_to_string(
                    "doc/statement/statement_template.md", {}
                )
                if markdown_content == default_content:
                    raise forms.ValidationError(
                        "The example content may not be saved. Edit it to contain the next revision statement content."
                    )
                if markdown_content == CONST_PDF_REV_NOTICE:
                    raise forms.ValidationError(
                        "Not proceeding with the text noting that the current version is pdf. Did you mean to upload a new PDF?"
                    )
        elif submission_method == "upload":
            if require_field("statement_file"):
                content_type = self.cleaned_data["statement_file"].content_type
                acceptable_types = (
                    "application/pdf",
                ) + settings.DOC_TEXT_FILE_VALID_UPLOAD_MIME_TYPES
                if not content_type.startswith(
                    acceptable_types
                ):  # dances around decoration of types with encoding etc.
                    self.add_error(
                        "statement_file",
                        forms.ValidationError(
                            f"Unexpected content type: Expected one of {', '.join(acceptable_types)}"
                        ),
                    )
                elif content_type != "application/pdf":
                    markdown_content = get_cleaned_text_file_content(
                        self.cleaned_data["statement_file"]
                    )
        if markdown_content != "":
            try:
                _ = markdown.liberal_markdown(markdown_content)
            except Exception as e:
                raise forms.ValidationError(f"Markdown processing failed: {e}")


@role_required("Secretariat")
def submit(request, name):
    statement = get_object_or_404(Document, type="statement", name=name)

    if request.method == "POST":
        form = StatementUploadForm(request.POST, request.FILES)
        if form.is_valid():
            statement_submission = form.cleaned_data["statement_submission"]
            writing_pdf = (
                statement_submission == "upload"
                and form.cleaned_data["statement_file"].content_type
                == "application/pdf"
            )

            statement.rev = "%02d" % (int(statement.rev) + 1)
            statement.uploaded_filename = (
                f"{statement.name}-{statement.rev}.{'pdf' if writing_pdf else 'md'}"
            )
            e = NewRevisionDocEvent.objects.create(
                type="new_revision",
                doc=statement,
                by=request.user.person,
                rev=statement.rev,
                desc="New revision available",
            )
            statement.save_with_history([e])
            markdown_content = ""
            if statement_submission == "upload":
                if not writing_pdf:
                    markdown_content = get_cleaned_text_file_content(
                        form.cleaned_data["statement_file"]
                    )
            else:
                markdown_content = form.cleaned_data["statement_content"]
            with Path(statement.get_file_name()).open(
                mode="wb" if writing_pdf else "w"
            ) as destination:
                if writing_pdf:
                    f = form.cleaned_data["statement_file"]
                    for chunk in f.chunks():
                        destination.write(chunk)
                    f.seek(0)
                    statement.store_file(statement.uploaded_filename, f)
                else:
                    destination.write(markdown_content)
                    statement.store_str(statement.uploaded_filename, markdown_content)
            return redirect("ietf.doc.views_doc.document_main", name=statement.name)
    else:
        if statement.uploaded_filename.endswith("pdf"):
            text = CONST_PDF_REV_NOTICE
        else:
            text = statement.text_or_error()
        init = {
            "statement_content": text,
            "statement_submission": "enter",
        }
        form = StatementUploadForm(initial=init)
    return render(
        request, "doc/statement/upload_content.html", {"form": form, "doc": statement}
    )


class NewStatementForm(StatementUploadForm):
    group = forms.ModelChoiceField(
        queryset=Group.objects.filter(acronym__in=["iab", "iesg"])
    )
    title = forms.CharField(max_length=255)
    field_order = [
        "group",
        "title",
        "statement_submission",
        "statement_file",
        "statement_content",
    ]

    def name_from_title_and_group(self, title, group):
        title_slug = xslugify(title)
        if title_slug.startswith(f"{group.acronym}-"):
            title_slug = title_slug[len(f"{group.acronym}-") :]
        name = f"statement-{group.acronym}-{title_slug[:240]}"
        return name.replace("_", "-")

    def clean(self):
        if all([field in self.cleaned_data for field in ["title", "group"]]):
            title = self.cleaned_data["title"]
            group = self.cleaned_data["group"]
            name = self.name_from_title_and_group(title, group)
            if name == self.name_from_title_and_group("", group):
                self.add_error(
                    "title",
                    forms.ValidationError(
                        "The filename derived from this title is empty. Please include a few descriptive words using ascii or numeric characters"
                    ),
                )
            if Document.objects.filter(name=name).exists():
                self.add_error(
                    "title",
                    forms.ValidationError(
                        "This title produces a filename already used by an existing statement"
                    ),
                )
        return super().clean()


@role_required("Secretariat")
def new_statement(request):
    if request.method == "POST":
        form = NewStatementForm(request.POST, request.FILES)
        if form.is_valid():
            statement_submission = form.cleaned_data["statement_submission"]
            writing_pdf = (
                statement_submission == "upload"
                and form.cleaned_data["statement_file"].content_type
                == "application/pdf"
            )

            group = form.cleaned_data["group"]
            title = form.cleaned_data["title"]
            name = form.name_from_title_and_group(title, group)
            statement = Document.objects.create(
                type_id="statement",
                group=group,
                name=name,
                title=title,
                abstract="",
                rev="00",
                uploaded_filename=f"{name}-00.{'pdf' if writing_pdf else 'md'}",
            )
            statement.set_state(State.objects.get(type_id="statement", slug="active"))
            e1 = NewRevisionDocEvent.objects.create(
                type="new_revision",
                doc=statement,
                by=request.user.person,
                rev=statement.rev,
                desc="New revision available",
                time=statement.time,
            )
            e2 = DocEvent.objects.create(
                type="published_statement",
                doc=statement,
                rev=statement.rev,
                by=request.user.person,
                desc="Statement published",
                time=statement.time,
            )
            statement.save_with_history([e1, e2])
            markdown_content = ""
            if statement_submission == "upload":
                if not writing_pdf:
                    markdown_content = get_cleaned_text_file_content(
                        form.cleaned_data["statement_file"]
                    )
            else:
                markdown_content = form.cleaned_data["statement_content"]
            with Path(statement.get_file_name()).open(
                mode="wb" if writing_pdf else "w"
            ) as destination:
                if writing_pdf:
                    f = form.cleaned_data["statement_file"]
                    for chunk in f.chunks():
                        destination.write(chunk)
                        f.seek(0)
                        statement.store_file(statement.uploaded_filename, f)
                else:
                    destination.write(markdown_content)
                    statement.store_str(statement.uploaded_filename, markdown_content)
            return redirect("ietf.doc.views_doc.document_main", name=statement.name)

    else:
        init = {
            "statement_content": escape(
                render_to_string(
                    "doc/statement/statement_template.md", {"settings": settings}
                )
            ),
            "statement_submission": "enter",
        }
        form = NewStatementForm(initial=init)
    return render(request, "doc/statement/new_statement.html", {"form": form})


@role_required("Secretariat")
def change_statement_state(request, name):
    """Change state of a statement Document"""
    statement = get_object_or_404(
        Document.objects.filter(type_id="statement"),
        name=name,
    )
    if request.method == "POST":
        form = ChangeStatementStateForm(request.POST)
        if form.is_valid():
            new_state = form.cleaned_data["state"]
            prev_state = statement.get_state()
            if new_state == prev_state:
                messages.info(request, f"State not changed, remains {prev_state}.")
            else:
                statement.set_state(new_state)
                e = add_state_change_event(
                    statement,
                    request.user.person,
                    prev_state,
                    new_state,
                )
                statement.save_with_history([e])
                messages.success(request, f"State changed to {new_state}.")
            return HttpResponseRedirect(statement.get_absolute_url())
    else:
        form = ChangeStatementStateForm(initial={"state": statement.get_state()})
    return render(
        request,
        "doc/statement/change_statement_state.html",
        {
            "form": form,
            "statement": statement,
        },
    )
